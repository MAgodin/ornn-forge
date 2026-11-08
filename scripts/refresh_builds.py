#!/usr/bin/env python3
"""Refresh champion/role builds using OP.GG's public MCP analysis tool.
Fail closed: do not replace previous builds with incomplete or invalid data.
Runs on GitHub Actions, with no token/paid API required.
"""
import concurrent.futures, datetime, json, re, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://mcp-api.op.gg/mcp"
DD = "https://ddragon.leagueoflegends.com"
POSITIONS = {"TOP":"top","JUNGLE":"jungle","MID":"mid","MIDDLE":"mid","ADC":"adc","BOTTOM":"adc","SUPPORT":"support","UTILITY":"support"}
FIELDS = [
    "data.core_items.{ids[],ids_names[],pick_rate,play,win}",
    "data.boots.{ids[],ids_names[],pick_rate,play,win}",
    "data.fourth_items[].{ids[],ids_names[],pick_rate,play,win}",
    "data.fifth_items[].{ids[],ids_names[],pick_rate,play,win}",
    "data.sixth_items[].{ids[],ids_names[],pick_rate,play,win}"
]
# Backup roles used only when a role breakdown cannot be fetched.
DEFAULT_ROLE = {
  "Viego":"jungle","Nocturne":"jungle","LeeSin":"jungle","MasterYi":"jungle",
  "Nunu":"jungle","Khazix":"jungle","Rengar":"jungle","Evelynn":"jungle",
  "Vi":"jungle","Warwick":"jungle","Fiddlesticks":"jungle",
  "Jinx":"adc","Caitlyn":"adc","Aphelios":"adc","Yunara":"adc",
  "Jhin":"adc","Draven":"adc","Vayne":"adc","Zeri":"adc",
  "Lulu":"support","Sona":"support","Soraka":"support",
  "Milio":"support","Nami":"support","Yuumi":"support",
  "Leona":"support","Rell":"support","Braum":"support",
  "Ahri":"mid","Syndra":"mid","Orianna":"mid","Zed":"mid",
  "Yasuo":"mid","Yone":"mid","Vex":"mid","Annie":"mid",
  "Aatrox":"top","Darius":"top","Fiora":"top","Garen":"top","Ornn":"top"
}

def get_json(url, retries=3):
    for n in range(retries):
        try:
            req = urllib.request.Request(url,headers={"User-Agent":"OrnnForge/1.0 (community build statistics; GitHub Actions)"})
            with urllib.request.urlopen(req,timeout=22) as r:
                return json.load(r)
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError, ValueError):
            if n == retries-1: raise
            time.sleep(2 + n*3)

def call(champ, position, fields):
    payload = {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
        "name":"lol_get_champion_analysis","arguments":{
            "champion":champ,"game_mode":"ranked","position":position,"desired_output_fields":fields
        }
    }}
    body=json.dumps(payload).encode()
    req=urllib.request.Request(ENDPOINT,data=body,headers={
        "Content-Type":"application/json","Accept":"application/json, text/event-stream",
        "User-Agent":"OrnnForge/1.0"
    },method="POST")
    try:
        with urllib.request.urlopen(req,timeout=28) as r: raw=r.read().decode("utf-8")
        if raw.startswith("event:") or raw.startswith("data:"):
            raw=next(line[5:].strip() for line in raw.splitlines() if line.startswith("data:"))
        result=json.loads(raw)
        if result.get("error") or result.get("result",{}).get("isError"): return ""
        return " ".join(c.get("text","") for c in result.get("result",{}).get("content",[]) if c.get("type")=="text")
    except (TimeoutError,urllib.error.URLError,ValueError,StopIteration):
        return ""

def roles(champ):
    raw=call(champ,"mid",["data.summary.positions[].name","data.summary.positions[].stats.play"])
    found=[]
    for name,plays in re.findall(r'Position\("([A-Z]+)",Stats\((\d+)',raw):
        p=POSITIONS.get(name)
        if p:found.append((p,int(plays)))
    found.sort(key=lambda v:-v[1])
    if found:
        best=found[0][1]
        return [pos for pos,count in found if count>=max(900,best*.22)][:2]
    return [DEFAULT_ROLE.get(champ,"mid")]

# Accept only standard purchasable legendary items. Never recommend boots,
# components, transformed Ornn outputs or special inventory items.
def eligible(item):
    gold=item.get("gold",{})
    tags=item.get("tags",[])
    return (gold.get("total",0)>=2350 and gold.get("purchasable",False)
        and item.get("maps",{}).get("11",False)
        and "Boots" not in tags and "Trinket" not in tags
        and not item.get("requiredAlly") and not item.get("hideFromAll",False)
        and item.get("depth",0)>=2
        and not item.get("specialRecipe")
    )

def parse_items(text, items):
    # OP.GG returns compact representations such as
    # CoreItems([6672,6676],[\"Kraken Slayer\",\"The Collector\"],0.12,10000,5300).
    groups=re.findall(r'CoreItems\(\[([0-9,\s]+)\],\[[^\]]*\],([0-9.]+),(\d+),(\d+)\)',text)
    out=[]
    for gi,(ids,pick,plays,wins) in enumerate(groups):
        # Group 0 = core, group 1 = boots, subsequent groups are later items.
        if gi==1:continue
        for raw_id in ids.split(","):
            if not raw_id.strip():continue
            num=int(raw_id.strip()); row=items.get(str(num))
            if not row or not eligible(row) or any(x["id"]==num for x in out):continue
            out.append({"id":num,"name":row["name"],"pickRate":float(pick),
                        "games":int(plays),"order":gi})
    return out[:8]

def main():
    versions=get_json(DD+"/api/versions.json")
    version=versions[0]
    champ_data=get_json(f"{DD}/cdn/{version}/data/en_US/champion.json")["data"]
    items=get_json(f"{DD}/cdn/{version}/data/en_US/item.json")["data"]
    champs=sorted(champ_data)
    existing={}
    if (ROOT/"builds.json").exists():
        try:existing=json.loads((ROOT/"builds.json").read_text()).get("champions",{})
        except (ValueError,OSError):pass

    def process(champ):
        all_roles={}
        for pos in roles(champ):
            text=call(champ,pos,FIELDS)
            build=parse_items(text,items)
            if len(build)>=2:all_roles[pos]={"items":build,"source":"OP.GG","games":max(i["games"] for i in build),"verified":True}
        return champ,all_roles

    results={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(process,c):c for c in champs}
        for future in concurrent.futures.as_completed(futures):
            name=futures[future]
            try:
                c,rows=future.result()
                if rows:results[c]=rows
            except Exception as e:print("Failed",name,str(e)[:100])
    print(f"Fetched {len(results)}/{len(champs)} champions on DDragon {version}")
    # Never destroy the last known successful set if OP.GG changes its format.
    if len(results)<max(80,int(len(champs)*.6)):
        raise SystemExit(f"Insufficient live coverage ({len(results)}); refusing update")
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    # Keep previous champion builds on temporary individual fetch errors, but
    # preserve per-entry fetch timestamp to prevent claims of fresh data.
    merged={}
    for champion in champs:
        if champion in results:
            merged[champion]={pos:{**val,"fetchedAt":now} for pos,val in results[champion].items()}
        elif champion in existing:
            merged[champion]=existing[champion]
    payload={"source":"OP.GG MCP","sourceUrl":"https://www.op.gg/",
             "version":version,"generatedAt":now,
             "freshCount":len(results),"totalChampions":len(champs),
             "champions":merged}
    (ROOT/"builds.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n")
    print("Saved",len(merged),"champions",sum(len(r) for r in merged.values()),"role builds")

if __name__=="__main__":main()
