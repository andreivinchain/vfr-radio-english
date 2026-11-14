#!/usr/bin/env python3
"""Генерация озвучки для VFR Radio English.
Требования: python3, ffmpeg, `pip install edge-tts`.
Запуск из корня репозитория:  python3 tools/gen_audio.py
Создаёт audio/<module>-<step>-atc.mp3, -atc2.mp3, -pilot.mp3 с «эфирным» фильтром.
Файлы необязательны: без них приложение использует браузерный TTS.
"""
import re, json, subprocess, asyncio, pathlib, sys
try:
    import edge_tts
except ImportError:
    sys.exit("pip install edge-tts")

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT/"index.html").read_text(encoding="utf-8")
js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
# вытаскиваем MODULES и функцию spoken() через node, чтобы не дублировать логику
node = """
const localStorage={getItem:()=>null,setItem:()=>{}};const window={};const speechSynthesis=undefined;
const document={querySelector:()=>({onclick:null,style:{},textContent:'',innerHTML:'',querySelectorAll:()=>[]}),createElement:()=>({remove(){},className:'',textContent:''}),body:{appendChild(){}}};
""" + js.replace("renderHome();", "") + """
const out=[];for(const m of MODULES)for(const [i,s] of m.steps.entries()){
 if(s.atc)out.push({f:`${m.id}-${i}-atc`,t:spoken(s.atc),v:'atc',station:s.atc});
 if(s.atc2)out.push({f:`${m.id}-${i}-atc2`,t:spoken(s.atc2),v:'atc',station:s.atc2});
 if(s.pilot)out.push({f:`${m.id}-${i}-pilot`,t:spoken(s.pilot),v:'pilot'});}
console.log(JSON.stringify(out));
"""
items = json.loads(subprocess.check_output(["node", "-e", node]))

VOICES = {  # разные голоса для разных станций — ближе к реальности
    "tower": "en-GB-RyanNeural", "ground": "en-GB-ThomasNeural", "delivery": "en-GB-ThomasNeural",
    "approach": "en-IE-ConnorNeural", "information": "en-GB-SoniaNeural", "radio": "en-GB-LibbyNeural",
    "atis": "en-GB-RyanNeural", "pilot": "en-US-GuyNeural", "default": "en-GB-RyanNeural",
}
def pick(it):
    if it["v"] == "pilot": return VOICES["pilot"]
    s = (it.get("station") or "").lower()
    for k, v in VOICES.items():
        if k in s: return v
    return VOICES["default"]

async def main():
    (ROOT/"audio").mkdir(exist_ok=True)
    for it in items:
        raw = ROOT/"audio"/(it["f"]+".raw.mp3"); out = ROOT/"audio"/(it["f"]+".mp3")
        if out.exists(): continue
        voice = pick(it); rate = "+5%" if it["v"] == "atc" else "+0%"
        await edge_tts.Communicate(it["t"], voice, rate=rate).save(str(raw))
        # «эфир»: полоса 300–3000 Гц, компрессия, лёгкий шум
        flt = ("highpass=f=300,lowpass=f=3000,acompressor=threshold=-18dB:ratio=4,volume=1.4,"
               "aresample=22050")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", flt,
                        "-b:a", "48k", str(out)], check=True)
        raw.unlink(); print("ok", out.name)
asyncio.run(main())
