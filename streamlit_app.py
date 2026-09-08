from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import json
import os
import streamlit as st
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
DATA = PROJECT_DIR / '.research_runs'
NOTEBOOK_PATH = PROJECT_DIR / 'competitor_analysis.ipynb'
ENV_PATH = PROJECT_DIR / '.env'
st.set_page_config(page_title='Competitor intelligence', page_icon='📊', layout='wide')

@st.cache_data(ttl=10, max_entries=64)
def load_json(path_text, modified_time):
    path = Path(path_text)
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except (OSError, ValueError, UnicodeError):
        return {}

def read_json(path):
    modified = path.stat().st_mtime if path.exists() else 0
    return load_json(str(path), modified)

def save_json_atomic(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

def evidence_ids(item):
    return [str(value) for value in item.get('evidence_ids', []) if value] if isinstance(item, dict) else []

def source_markdown(ids, source_index):
    links=[]; seen=set()
    for source_id in ids:
        source=source_index.get(source_id)
        if not source: continue
        url=str(source.get('url') or '').strip()
        title=str(source.get('title') or url or 'Source').replace('[','').replace(']','')
        marker=(title,url)
        if marker in seen: continue
        seen.add(marker); links.append(f'[{title}]({url})' if url else title)
    return ' · '.join(links)

def show_sources(item, source_index):
    links=source_markdown(evidence_ids(item),source_index)
    if links: st.markdown(f':material/link: **Sources:** {links}')

def selected_markdown(target, analysis, source_index, as_of):
    lines=[f'# {target}: {analysis.get("name","Selected competitor")}', '', f'As of: {as_of}', '']
    for heading,item in [('Pricing',analysis.get('pricing',{})),('Market positioning',analysis.get('positioning',{}))]:
        lines.extend([f'## {heading}',str(item.get('value') or 'Not available.'),''])
    lines.append('## Core features')
    lines.extend([f'- {item.get("value","Not available.")}' for item in analysis.get('features',[])] or ['- Not available.'])
    lines.extend(['','## Recent news'])
    news=analysis.get('recent_news',[])
    lines.extend([f'- {item.get("value","Not available.")}' for item in news] or ['- No recent news was captured.'])
    lines.extend(['','## Sources'])
    used=[]
    for item in [analysis.get('pricing',{}),analysis.get('positioning',{}),*analysis.get('features',[]),*news]: used.extend(evidence_ids(item))
    lines.append(source_markdown(used,source_index) or 'No linked sources were captured.')
    return '\n'.join(lines)

@st.cache_resource
def load_notebook_backend():
    if not NOTEBOOK_PATH.exists():
        raise RuntimeError(f'Notebook not found: {NOTEBOOK_PATH}')
    load_dotenv(ENV_PATH, override=True)
    notebook=json.loads(NOTEBOOK_PATH.read_text(encoding='utf-8-sig'))
    namespace={'__name__':'competitor_notebook_backend','__file__':str(NOTEBOOK_PATH)}
    for cell_index in (8,12,16,19,21,24,27):
        source=''.join(notebook['cells'][cell_index].get('source',[]))
        exec(compile(source,f'{NOTEBOOK_PATH.name}:cell-{cell_index}','exec'),namespace)
    execute_source=''.join(notebook['cells'][29].get('source',[]))
    marker="research_run={'status':'not_started'}"
    if marker not in execute_source:
        raise RuntimeError('The Step 9 execution boundary could not be found.')
    exec(compile(execute_source.split(marker,1)[0],f'{NOTEBOOK_PATH.name}:cell-29-definitions','exec'),namespace)
    namespace['HERE']=PROJECT_DIR
    namespace['DATA']=DATA
    namespace['MODEL_NAME']=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
    namespace['MAX_RUN_SECONDS']=900
    return namespace

def execute_research(company, context, freshness, on_progress):
    company=company.strip(); context=context.strip()
    if not 2 <= len(company) <= 200:
        return {'status':'failed','message':'Enter a target company between 2 and 200 characters.'}
    if len(context)>4000:
        return {'status':'failed','message':'Keep the market context below 4,000 characters.'}
    if freshness not in {'day','week','month','year'}:
        return {'status':'failed','message':'Select a valid news window.'}
    backend=load_notebook_backend(); run_id=uuid4().hex
    inputs={'company':company,'context':context,'freshness':freshness,'as_of':datetime.now(timezone.utc).date().isoformat()}
    backend['start_run_budget'](backend['MAX_RUN_SECONDS'])
    missing=[name for name in ('OPENAI_API_KEY','YOU_API_KEY') if not os.getenv(name,'').strip()]
    simulation=bool(missing)
    try:
        if simulation:
            on_progress('Credentials unavailable; starting the clearly labeled simulator.')
            result,topology,history=backend['execute_simulated_research'](run_id,inputs,progress=on_progress)
        else:
            on_progress('Starting live OpenAI and You.com research.')
            model=backend['ChatOpenAI'](model=backend['MODEL_NAME'],timeout=backend['REQUEST_TIMEOUT'][1],max_retries=0)
            search=backend['YouSearch'](os.environ['YOU_API_KEY'])
            result,topology,history=backend['execute_run'](run_id,model,search,inputs,progress=on_progress)
        exported_status='simulated' if simulation else ('completed' if result.get('status')=='complete' else 'needs_review')
        mode='simulation' if simulation else 'live'
        save_json_atomic(DATA/f'{run_id}.json',result)
        markdown_path=DATA/f'{run_id}.md'; temporary=markdown_path.with_suffix('.md.tmp')
        temporary.write_text(result.get('markdown',''),encoding='utf-8'); temporary.replace(markdown_path)
        save_json_atomic(DATA/f'{run_id}_status.json',{'status':exported_status,'mode':mode,'run_id':run_id,'company':company,'updated_at':datetime.now(timezone.utc).isoformat(),'message':'Research run exported.'})
        on_progress('Research files saved. Opening the new result.')
        return {'status':exported_status,'mode':mode,'run_id':run_id,'result':result,'topology':topology,'history':history}
    except Exception as exc:
        failure=backend['classify_failure'](exc,'Competitor research')
        message=backend['failure_message'](failure)
        save_json_atomic(DATA/f'{run_id}_status.json',{'status':'failed','code':failure.code,'message':message,'run_id':run_id,'company':company,'updated_at':datetime.now(timezone.utc).isoformat()})
        return {'status':'failed','run_id':run_id,'message':message}

def short_text(value, limit=260):
    text = ' '.join(str(value or '').split())
    if not text:
        return 'Not available.'
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(' ', 1)[0]
    return clipped + '...'

def run_ids():
    return sorted({path.stem for path in DATA.glob('*.json') if not path.name.startswith('_') and not path.name.endswith('_status.json')},key=lambda value:(DATA/f'{value}.json').stat().st_mtime,reverse=True)

def run_label(run_id):
    state=read_json(DATA/f'{run_id}.json'); status=read_json(DATA/f'{run_id}_status.json')
    company=str(state.get('company') or status.get('company') or 'Unknown company')
    as_of=str(state.get('as_of') or str(status.get('updated_at') or '')[:10] or 'Unknown date')
    label=str(status.get('status') or state.get('status') or 'unknown').replace('_',' ').title()
    return f'{company} | {as_of} | {label}'

st.title('Competitor intelligence')
st.caption('Enter one target company. The agents discover three relevant competitors; the result page displays one selected competitor at a time.')
with st.form('new_research',border=True):
    st.subheader('Start new research')
    target_input=st.text_input('Target company',placeholder='Example: Microsoft, Notion, Salesforce')
    context_input=st.text_area('Market and audience context',value='Products, pricing, positioning, and recent news for business decision-making',max_chars=4000)
    freshness_input=st.selectbox('Recent-news window',['month','week','day','year'],key='new_freshness')
    submitted=st.form_submit_button('Run competitor research',type='primary',icon=':material/search:')

if submitted:
    if len(target_input.strip())<2:
        st.error('Enter a target company before running research.')
    else:
        with st.status(f'Researching {target_input.strip()}...',expanded=True) as progress_box:
            progress_box.write('Validating input and preparing the LangGraph workflow.')
            outcome=execute_research(target_input,context_input,freshness_input,lambda message:progress_box.write(str(message).replace('_',' ').title()))
            if outcome.get('status')=='failed':
                progress_box.update(label='Research could not be completed',state='error',expanded=True)
                st.error(outcome.get('message','Research failed.'))
            else:
                progress_box.update(label='Research completed',state='complete',expanded=False)
                st.session_state['preferred_run']=outcome['run_id']
                load_json.clear(); st.rerun()

available_runs=run_ids()
if not available_runs:
    st.info('No saved results yet. Enter a target company above and start research.')
    st.stop()
preferred=st.session_state.pop('preferred_run',None)
selected_index=available_runs.index(preferred) if preferred in available_runs else 0
with st.sidebar:
    st.title('Saved research')
    st.caption('Select a previous target-company run.')
    selected_run=st.selectbox('Research run',available_runs,index=selected_index,format_func=run_label,key='saved_run')

state=read_json(DATA/f'{selected_run}.json'); run_status=read_json(DATA/f'{selected_run}_status.json')
analyses=[item for item in state.get('analyses',[]) if isinstance(item,dict) and item.get('name')]
if not analyses:
    st.error('This run does not contain competitor analysis records.')
    st.stop()
competitor_names=[str(item['name']) for item in analyses]
selected_name=st.sidebar.selectbox('Select one competitor',competitor_names,key=f'competitor_{selected_run}')
analysis=next(item for item in analyses if str(item.get('name'))==selected_name)
target_company=str(state.get('company') or 'Unknown target')
status=str(run_status.get('status') or state.get('status') or 'unknown')
mode=str(run_status.get('mode') or ('simulation' if status=='simulated' else 'live'))
all_sources=[*(state.get('discovery_sources') or []),*((state.get('research') or {}).get(selected_name) or [])]
source_index={str(item.get('id')):item for item in all_sources if isinstance(item,dict) and item.get('id')}

st.header(f'Research target: {target_company}')
st.caption(f'Viewing one selected competitor: **{selected_name}**')
if mode=='simulation' or status=='simulated': st.warning('Simulation only: this run contains synthetic workflow data, not live market research.')
elif status=='completed': st.success('Live competitor research completed.')
elif status=='needs_review': st.warning('Research completed with review items. Check the review section below.')
with st.container(horizontal=True):
    st.metric('Target company',target_company,border=True)
    st.metric('Selected competitor',selected_name,border=True)
    st.metric('Status',status.replace('_',' ').title(),border=True)
    st.metric('As of',str(state.get('as_of') or 'Unknown'),border=True)

pricing_summary = short_text((analysis.get('pricing') or {}).get('value'))
positioning_summary = short_text((analysis.get('positioning') or {}).get('value'))
feature_values = [short_text(item.get('value'), 150) for item in (analysis.get('features') or [])[:2]]
news_items = analysis.get('recent_news') or []
news_summary = short_text(news_items[0].get('value'), 220) if news_items else 'No recent news was captured.'
with st.container(border=True):
    st.subheader('Quick summary')
    st.markdown(f'**{selected_name}** is being evaluated as a competitor to **{target_company}**.')
    st.markdown(f'- **Pricing:** {pricing_summary}')
    st.markdown(f'- **Positioning:** {positioning_summary}')
    st.markdown(f'- **Key capabilities:** {"; ".join(feature_values) if feature_values else "No core features were captured."}')
    st.markdown(f'- **Latest news:** {news_summary}')

with st.expander('Detailed analysis', expanded=False):
    competitor_record=next((item for item in state.get('competitors',[]) if str(item.get('name'))==selected_name),{})
    with st.container(border=True):
        st.header(selected_name)
        website=str(competitor_record.get('website') or '').strip()
        if website: st.markdown(f':material/language: [{website}]({website})')
        rationale=str(competitor_record.get('rationale') or '').strip()
        if rationale: st.write(rationale); show_sources(competitor_record,source_index)
    for heading,key in [('Pricing','pricing'),('Market positioning','positioning')]:
        with st.container(border=True):
            st.subheader(heading); item=analysis.get(key) or {}; st.write(item.get('value') or f'{heading} information was not available.'); show_sources(item,source_index)
    with st.container(border=True):
        st.subheader('Core features'); features=analysis.get('features') or []
        if not features: st.info('No core features were captured.')
        for feature in features: st.markdown(f'- {feature.get("value") or "Feature details unavailable."}'); show_sources(feature,source_index)
    with st.container(border=True):
        st.subheader('Recent news'); news=analysis.get('recent_news') or []
        if not news: st.info('No recent news was captured for this competitor.')
        for index,item in enumerate(news,1): st.markdown(f'**{index}.** {item.get("value") or "News details unavailable."}'); show_sources(item,source_index)
review=state.get('review') or {}; issues=[str(item) for item in review.get('issues',[]) if item]; gaps=[str(item) for item in analysis.get('gaps',[]) if item]
if issues or gaps:
    with st.expander('Review notes and research gaps'):
        if issues:
            st.markdown('**Critic review**')
            for issue in issues: st.markdown(f'- {issue}')
        if gaps:
            st.markdown('**Selected competitor gaps**')
            for gap in gaps: st.markdown(f'- {gap}')
with st.expander('Sources used for this selected competitor'):
    if not source_index: st.info('No source records were captured for this competitor.')
    for source in source_index.values():
        title=str(source.get('title') or source.get('url') or 'Source'); url=str(source.get('url') or '').strip(); kind=str(source.get('kind') or 'web').title()
        st.markdown(f'- **{kind}:** [{title}]({url})' if url else f'- **{kind}:** {title}')
selected_payload={'target_company':target_company,'selected_competitor':selected_name,'as_of':state.get('as_of'),'status':status,'analysis':analysis,'sources':list(source_index.values())}
selected_md=selected_markdown(target_company,analysis,source_index,state.get('as_of') or 'Unknown')
with st.container(border=True):
    st.subheader('Download selected competitor')
    with st.container(horizontal=True):
        safe_name=selected_name.lower().replace(' ','_')
        st.download_button('Download Markdown',data=selected_md,file_name=f'{safe_name}_analysis.md',mime='text/markdown')
        st.download_button('Download JSON',data=json.dumps(selected_payload,ensure_ascii=False,indent=2),file_name=f'{safe_name}_analysis.json',mime='application/json')
