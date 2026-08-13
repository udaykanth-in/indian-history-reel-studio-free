import os, re, json, time, base64, zipfile, io
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st

APP = Path(__file__).parent
OUT = APP / 'output'
OUT.mkdir(exist_ok=True)
HORDE = 'https://stablehorde.net/api'
ANON_KEY = '0000000000'

st.set_page_config(page_title='Indian History Reel Studio — Free', page_icon='🎬', layout='wide')

SYSTEM = '''You are the Master Indian History Reel Agent.
Communication with the user is English.
Viewer-facing narration, subtitles, and on-screen text are natural modern Telugu.
Historical figures never speak. Only a third-person narrator speaks.
Production is still images + Telugu narration + music/SFX. No video prompts.
Only verified claims may be presented as established fact. Separate legends, disputed claims, and uncertainty.
Never invent dialogue, quotations, thoughts, conversations, motivations, statistics, or historical details.
Visual continuity is mandatory: recurring character identity, age, physique, costume, accessories, weapons, locations, architecture, environment, geography, weather, lighting, period, and cinematic treatment must stay coherent.
Every image must be numbered and synchronized to exact narration time ranges.'''


def horde_post(path, payload):
    r = requests.post(HORDE + path, json=payload, headers={
        'apikey': ANON_KEY,
        'Client-Agent': 'IndianHistoryReelStudio:1.0'
    }, timeout=60)
    r.raise_for_status()
    return r.json()


def horde_text(prompt, max_wait=240):
    payload = {
        'prompt': prompt,
        'params': {
            'max_length': 2200,
            'max_context_length': 8192,
            'temperature': 0.35,
            'top_p': 0.9,
        },
        'trusted_workers': True,
        'nsfw': False,
        'models': []
    }
    job = horde_post('/v2/generate/text/async', payload)
    jid = job['id']
    started = time.time()
    while time.time() - started < max_wait:
        s = requests.get(HORDE + f'/v2/generate/text/status/{jid}', headers={'Client-Agent':'IndianHistoryReelStudio:1.0'}, timeout=30).json()
        if s.get('done') and s.get('generations'):
            return s['generations'][0]['text']
        time.sleep(4)
    raise TimeoutError('Free text generation queue took too long. Please retry.')


def horde_image(prompt, out_file, max_wait=600):
    payload = {
        'prompt': prompt,
        'params': {
            'width': 704,
            'height': 1024,
            'steps': 25,
            'n': 1,
            'cfg_scale': 7.0,
            'sampler_name': 'k_euler',
        },
        'nsfw': False,
        'trusted_workers': True,
        'models': []
    }
    job = horde_post('/v2/generate/async', payload)
    jid = job['id']
    started = time.time()
    while time.time() - started < max_wait:
        s = requests.get(HORDE + f'/v2/generate/status/{jid}', headers={'Client-Agent':'IndianHistoryReelStudio:1.0'}, timeout=30).json()
        if s.get('done') and s.get('generations'):
            img = s['generations'][0].get('img')
            if not img:
                raise RuntimeError('Free image service returned no image URL.')
            raw = requests.get(img, timeout=120).content
            out_file.write_bytes(raw)
            return
        time.sleep(5)
    raise TimeoutError('Free image generation queue took too long. Retry this image.')


WIKI_HEADERS = {
    "User-Agent": "IndianHistoryReelStudio/1.1 (educational history reel app; contact: local-user)",
    "Accept": "application/json",
}


def wiki_get(url, params, attempts=4, timeout=30):
    last = None
    for attempt in range(attempts):
        try:
            r = requests.get(url, params=params, headers=WIKI_HEADERS, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                retry_after = r.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.replace('.', '', 1).isdigit() else min(2 ** attempt, 12)
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            if attempt < attempts - 1:
                time.sleep(min(2 ** attempt, 8))
    raise last or RuntimeError("Wikipedia request failed")


def wiki_search(topic):
    url = 'https://en.wikipedia.org/w/api.php'
    params = {'action':'query','list':'search','srsearch':topic,'srlimit':5,'format':'json','utf8':1}
    r = wiki_get(url, params)
    data = r.json()
    return [x['title'] for x in data.get('query', {}).get('search', [])]


def wiki_extract(title):
    url = 'https://en.wikipedia.org/w/api.php'
    params = {'action':'query','prop':'extracts|info','explaintext':1,'inprop':'url','titles':title,'format':'json','redirects':1}
    r = wiki_get(url, params)
    pages = r.json().get('query', {}).get('pages', {})
    if not pages:
        return {'title':title,'extract':'','url':''}
    p = next(iter(pages.values()))
    return {'title':p.get('title',title),'extract':p.get('extract',''),'url':p.get('fullurl','')}


def extract_json(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def call_agent(prompt, attempts=2):
    last = None
    for _ in range(attempts):
        try:
            return horde_text(SYSTEM + '\n\n' + prompt)
        except Exception as e:
            last = e
    raise last


def research(topic, supplied_sources):
    sources = []
    research_warning = ''
    try:
        titles = wiki_search(topic)
        sources = [wiki_extract(t) for t in titles[:5]]
    except Exception as e:
        research_warning = f"Public Wikipedia retrieval failed temporarily: {type(e).__name__}. Do not treat this as evidence. Use user-supplied sources if available and clearly mark confidence lower."

    evidence = '\n\n'.join(f"SOURCE: {s['title']}\nURL: {s['url']}\n{s['extract'][:7000]}" for s in sources if s.get('extract'))
    if research_warning:
        evidence += '\n\nRESEARCH WARNING:\n' + research_warning
    if supplied_sources.strip():
        evidence += '\n\nUSER-SUPPLIED SOURCES/EVIDENCE:\n' + supplied_sources[:16000]
    if not evidence.strip():
        evidence = 'No public-source evidence was retrieved. Do not invent facts. Return an evidence-limited research package and mark confidence appropriately.'
    prompt = f'''Conduct a careful historical research pass for: {topic}

Public-source evidence retrieved from Wikipedia/Wikimedia API and any user-supplied source text is below.
Do not treat Wikipedia as perfect authority. Mark claims requiring stronger verification.

{evidence}

Return JSON with:
topic, one_sentence_summary, historical_context, why_it_matters, timeline(list of date,event,significance), key_people, key_locations, verified_facts, partially_verified_claims, disputed_claims, common_myths(list of myth,historical_evidence), references, confidence_score.
Only classify a claim as VERIFIED when the supplied evidence is sufficient. Use English for the research package.'''
    return extract_json(call_agent(prompt))


def create_story(kb, duration, style):
    prompt = f'''Create a {duration}-second short-form historical documentary from this approved research package.
STYLE: {style}

Rules:
- Narration only. No historical character speaks.
- Narration must be natural modern Telugu.
- Use only VERIFIED facts as established facts.
- Do not invent dialogue, quotations, thoughts, conversations, motivations, statistics, or dramatic details.
- Keep timing realistic for spoken Telugu. Target the requested duration.
- Create curiosity without misleading the viewer.

APPROVED RESEARCH:
{json.dumps(kb, ensure_ascii=False, indent=2)}

Return JSON:
{{"title":"English title","hook_telugu":"","setup_telugu":"","beat1_telugu":"","beat2_telugu":"","beat3_telugu":"","resolution_telugu":"","outro_telugu":"","voiceover_telugu":""}}'''
    return extract_json(call_agent(prompt))


def visual_bible(kb, story):
    prompt = f'''Create an internal Visual Bible for a still-image historical documentary.

RESEARCH:
{json.dumps(kb, ensure_ascii=False, indent=2)}

STORY:
{json.dumps(story, ensure_ascii=False, indent=2)}

Return JSON with:
characters, locations, costume_rules, environment_rules, timeline_rules, cinematic_rules.
For uncertain historical appearance, say "historically plausible representation" rather than inventing a claimed portrait.'''
    return extract_json(call_agent(prompt))


def scene_plan(kb, story, bible, duration):
    prompt = f'''Create an editing-ready image sequence for a {duration}-second reel.

RESEARCH:
{json.dumps(kb, ensure_ascii=False, indent=2)}
STORY:
{json.dumps(story, ensure_ascii=False, indent=2)}
VISUAL BIBLE:
{json.dumps(bible, ensure_ascii=False, indent=2)}

Rules:
- 7 to 10 still images.
- Exact timestamps must start at 0 and end at {duration} seconds.
- Duration of images can vary based on narration.
- Each image change should match a meaningful change in the narration.
- Narration segment in Telugu.
- All visual/technical descriptions and image prompts in English.
- On-screen text in Telugu.
- Every recurring character/location must inherit the Visual Bible.
- No new facts.

Return JSON: {{"scenes":[{{"image_number":1,"start":0,"end":4,"duration":4,"voiceover_segment":"","visual_purpose":"","visual_description":"","characters":"","costume":"","location":"","period":"","camera":"","lighting":"","environment":"","image_prompt":"","motion_suggestion":"","sfx":"","music":"","onscreen_text":""}}]}}'''
    return extract_json(call_agent(prompt))['scenes']


def srt(text, duration):
    parts = [p.strip() for p in re.split(r'(?<=[.!?।])\s+', text) if p.strip()]
    if not parts: return ''
    weights = [max(1, len(p)) for p in parts]
    total = sum(weights)
    cur = 0
    def fmt(x):
        h=int(x//3600); m=int((x%3600)//60); s=int(x%60); ms=int((x-int(x))*1000)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    rows=[]
    for i,p in enumerate(parts,1):
        d=duration*weights[i-1]/total
        rows.append(f'{i}\n{fmt(cur)} --> {fmt(cur+d)}\n{p}\n')
        cur += d
    return '\n'.join(rows)


def zip_project(slug):
    p = OUT / slug
    zp = OUT / f'{slug}.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in p.rglob('*'):
            if f.is_file(): z.write(f, f.relative_to(p.parent))
    return zp

st.title('🎬 Indian History Reel Studio — Free Mode')
st.caption('No OpenAI API key. Uses public research, free community AI generation, and optional free Telugu TTS.')

with st.sidebar:
    st.header('Reel Setup')
    topic = st.text_input('Topic', 'Chhatrapati Shivaji Maharaj’s early rise')
    audience = st.text_input('Audience', 'General audience')
    duration = st.number_input('Duration (seconds)', 15, 120, 45, 5)
    style = st.selectbox('Style', ['Cinematic Historical Documentary','Suspense Documentary','Epic Historical Documentary','Emotional Historical Documentary'])
    series = st.text_input('Series name', '')
    episode = st.text_input('Episode', '')
    supplied = st.text_area('Optional source URLs / notes / pasted evidence', '')
    do_images = st.checkbox('Generate actual AI images (free, may be slow)', True)
    do_tts = st.checkbox('Generate Telugu MP3 voiceover (optional)', True)
    go = st.button('🚀 Generate Free Reel', type='primary', use_container_width=True)

if go:
    slug = re.sub(r'[^a-z0-9]+','-',topic.lower()).strip('-') + '-' + time.strftime('%Y%m%d%H%M%S')
    project = OUT / slug
    images = project / 'images'; images.mkdir(parents=True, exist_ok=True)
    (project/'audio').mkdir(exist_ok=True)
    with st.status('Generating free reel...', expanded=True) as stx:
        st.write('1/5 Researching public sources...')
        kb = research(topic, supplied)
        st.write('2/5 Creating Telugu narration...')
        story = create_story(kb, duration, style)
        st.write('3/5 Building Visual Bible...')
        bible = visual_bible(kb, story)
        st.write('4/5 Building timed image sequence...')
        scenes = scene_plan(kb, story, bible, duration)
        img_done=[]
        if do_images:
            for s in scenes:
                n=int(s['image_number'])
                st.write(f'Generating IMAGE {n:02d} ... Free queue may be slow.')
                prompt = s['image_prompt'] + '\n\nCONTINUITY LOCK:\n' + json.dumps(bible, ensure_ascii=False)
                try:
                    horde_image(prompt, images/f'IMAGE_{n:02d}.png')
                    img_done.append(n)
                except Exception as e:
                    st.warning(f'IMAGE {n:02d} failed: {e}')
        audio_path=None
        if do_tts:
            try:
                import edge_tts
                audio_path=project/'audio'/'voiceover_te-IN-ShrutiNeural.mp3'
                communicate=edge_tts.Communicate(story['voiceover_telugu'], 'te-IN-ShrutiNeural')
                import asyncio
                asyncio.run(communicate.save(str(audio_path)))
            except Exception as e:
                st.warning(f'TTS was not generated. You still have the Telugu script. Reason: {e}')
        (project/'research.json').write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding='utf-8')
        (project/'story.json').write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding='utf-8')
        (project/'visual_bible.json').write_text(json.dumps(bible, ensure_ascii=False, indent=2), encoding='utf-8')
        (project/'scenes.json').write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding='utf-8')
        (project/'voiceover_telugu.txt').write_text(story['voiceover_telugu'], encoding='utf-8')
        (project/'subtitles.srt').write_text(srt(story['voiceover_telugu'], duration), encoding='utf-8')
        lines=['image,start,end,duration,voiceover']
        for s in scenes:
            lines.append(f"IMAGE_{int(s['image_number']):02d},{s['start']},{s['end']},{s['duration']},\"{s['voiceover_segment'].replace(chr(34), chr(34)*2)}\"")
        (project/'editing_timeline.csv').write_text('\n'.join(lines), encoding='utf-8')
        zp=zip_project(slug)
        stx.update(label='Free reel package complete', state='complete')
    st.session_state['result']={'kb':kb,'story':story,'bible':bible,'scenes':scenes,'zip':zp,'project':project}

if 'result' in st.session_state:
    r=st.session_state['result']
    tabs=st.tabs(['Research','Telugu Script','Visual Bible','Image Timeline','Export'])
    with tabs[0]: st.json(r['kb'])
    with tabs[1]: st.text_area('Clean Telugu narration', r['story']['voiceover_telugu'], height=260)
    with tabs[2]: st.json(r['bible'])
    with tabs[3]:
        for s in r['scenes']:
            n=int(s['image_number'])
            st.markdown(f"### IMAGE {n:02d} — {s['start']}s–{s['end']}s")
            st.write(s['visual_description'])
            p=r['project']/ 'images' / f'IMAGE_{n:02d}.png'
            if p.exists(): st.image(str(p), width=300)
            st.code(s['image_prompt'], language='text')
            st.caption(f"Narration: {s['voiceover_segment']} | Motion: {s['motion_suggestion']}")
    with tabs[4]:
        zp=r['zip']
        st.download_button('⬇️ Download complete project ZIP', zp.read_bytes(), file_name=zp.name, mime='application/zip')
        st.download_button('⬇️ Telugu voiceover text', r['story']['voiceover_telugu'], file_name='voiceover_telugu.txt')
        st.download_button('⬇️ Subtitles', srt(r['story']['voiceover_telugu'], duration), file_name='subtitles.srt')
else:
    st.info('Enter a topic and click Generate Free Reel.')
    st.markdown('### Free stack')
    st.write('Research: public Wikipedia/Wikimedia API. Text and image generation: AI Horde community service. Telugu TTS: optional edge-tts using the Telugu neural voice. Free services can be slower or change availability.')
