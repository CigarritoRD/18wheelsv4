"""Offline Chromium UI integration test using a TestClient transport bridge.

No live browser HTTP/cookie transport or native localStorage is exercised here.
The real FastAPI handlers, SQLite sessions and permissions are exercised.
"""
from pathlib import Path
import base64
import contextlib
import json
import os
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app.server import create_app
APP=None
OUT=ROOT/'docs'
TEMP='temporary-private-2026'
FINAL='final-browser-password-2026'
checks=[]

def check(value,message):
    assert value,message
    checks.append(message)

def wait_detail(page, state):
    page.locator('.detail-header .status-badge').filter(has_text=state).wait_for()


BRIDGE_JS=r"""
window.fetch=async(url,opts={})=>{
 const packet={url:String(url),method:opts.method||'GET',headers:opts.headers||{}};
 if(opts.body instanceof FormData){
  packet.fields={};packet.files=[];
  for(const [key,value] of opts.body.entries()){
   if(value instanceof File){const bytes=new Uint8Array(await value.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);packet.files.push({field:key,name:value.name,type:value.type,base64:btoa(binary)});}
   else packet.fields[key]=value;
  }
 }else if(opts.body!==undefined)packet.body=opts.body;
 const reply=await window._offlineCall(packet);
 const content=reply.json!==undefined?JSON.stringify(reply.json):Uint8Array.from(atob(reply.base64),c=>c.charCodeAt(0));
 return new Response(content,{status:reply.status,headers:reply.headers});
};
"""

def load_app(page,client=None):
    if client is not None:
        page._backend_client=client
        def transport(packet):
            client=page._backend_client
            kwargs={'headers':packet.get('headers',{})}
            if 'files' in packet:
                kwargs['data']=packet.get('fields',{})
                kwargs['files']=[(f['field'],(f['name'],base64.b64decode(f['base64']),f['type'])) for f in packet['files']]
            elif 'body' in packet:kwargs['content']=packet['body']
            reply=client.request(packet['method'],packet['url'],**kwargs)
            result={'status':reply.status_code,'headers':{'content-type':reply.headers.get('content-type','application/octet-stream')}}
            if 'application/json' in reply.headers.get('content-type',''):
                def images(value):
                    if isinstance(value,dict):return {k:images(v) for k,v in value.items()}
                    if isinstance(value,list):return [images(v) for v in value]
                    if isinstance(value,str) and value.startswith('/photos/'):
                        photo=client.get(value)
                        return 'data:image/jpeg;base64,'+base64.b64encode(photo.content).decode() if photo.status_code==200 else value
                    return value
                result['json']=images(reply.json())
            else:result['base64']=base64.b64encode(reply.content).decode()
            return result
        page.expose_function('_offlineCall',transport)
    html=(ROOT/'app/static/index.html').read_text()
    html=html.replace('<link rel="stylesheet" href="/static/style.css">','<style>'+(ROOT/'app/static/style.css').read_text()+'</style>')
    html=html.replace('<script defer src="/static/app.js"></script>','')
    html=html.replace('</body>','<script>'+BRIDGE_JS+'</script><script>'+(ROOT/'app/static/app.js').read_text()+'</script></body>')
    page.goto('about:blank');page.set_content(html)


def load_demo(page,preserve=False):
    state=page.evaluate('window._offlineStorage') if preserve else {}
    storage_js='window._offlineStorage='+json.dumps(state)+';'+"""
    Object.defineProperty(window,'localStorage',{value:{
      getItem:key=>window._offlineStorage[key]??null,
      setItem:(key,value)=>{window._offlineStorage[key]=String(value);},
      removeItem:key=>{delete window._offlineStorage[key];}
    }});
    """
    html=(ROOT/'18wheelers-preview.html').read_text().replace('<head>','<head><script>'+storage_js+'</script>',1)
    page.goto('about:blank');page.set_content(html)

def sign_in(browser,url,email):
    context=browser.new_context(viewport={'width':1440,'height':1000})
    context.set_default_timeout(8000)
    page=context.new_page();load_app(page,TestClient(APP))
    page.locator('input[name=email]').fill(email)
    page.locator('input[name=password]').fill(TEMP)
    page.locator('button[type=submit]').click()
    page.locator('input[name=current_password]').fill(TEMP)
    page.locator('input[name=new_password]').fill(FINAL)
    page.locator('input[name=confirm_password]').fill(FINAL)
    page.locator('button[type=submit]').click()
    page.locator('.shell').wait_for()
    return context,page


def main():
    global APP
    OUT.mkdir(exist_ok=True)
    errors=[]
    with tempfile.TemporaryDirectory(prefix='18w-role-offline-') as temp:
        data=Path(temp)/'data';photo=Path(temp)/'test-photo.jpg'
        Image.new('RGB',(120,80),(180,190,200)).save(photo)
        APP=create_app(data)
        url='offline-test'
        with contextlib.nullcontext():
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EW_BROWSER_PATH') or shutil.which('chromium'))
                browser.on('disconnected',lambda:None)
                admin_context=browser.new_context(viewport={'width':1440,'height':1000})
                admin_context.set_default_timeout(8000)
                admin=admin_context.new_page();admin.on('pageerror',lambda error:errors.append(str(error)))
                admin_client=TestClient(APP)
                csrf=admin_client.get('/api/session').json()['csrf']
                result=admin_client.post('/api/setup',headers={'x-csrf-token':csrf},json={'name':'Demo Admin','email':'admin@example.test','password':FINAL,'setup_token':(data/'.setup-token').read_text()})
                check(result.status_code==200,'Initial administrator setup through API')
                load_app(admin,admin_client)
                admin.locator('.shell').wait_for()
                check(admin.locator('.account small').inner_text()=='Admin','Initial administrator screen')
                admin.locator('[data-action=nav][data-page=team]').click()
                for index,(name,email,role) in enumerate([('Carlos Technician','tech@example.test','technician'),('Demo Requester','requester@example.test','requester')],start=2):
                    admin.locator('[data-action=new-user]').click()
                    check(admin.locator('select[name=role]').input_value()=='requester','New accounts default to Requester')
                    check(admin.locator('select[name=role] option').all_text_contents()==['Admin','Technician','Requester'],'Exactly three selectable roles')
                    admin.locator('input[name=name]').fill(name);admin.locator('input[name=email]').fill(email)
                    admin.locator('select[name=role]').select_option(role);admin.locator('input[name=password]').fill(TEMP)
                    admin.locator('button[form=user-form][type=submit]').click()
                    admin.locator('.team-card').nth(index-1).wait_for()
                admin.screenshot(path=str(OUT/'three-roles-admin-team.png'),full_page=True)
                csrf=admin_client.get('/api/session').json()['csrf']
                private=admin_client.post('/api/jobs',headers={'x-csrf-token':csrf},json={'title':'Private admin-only job'})
                check(private.status_code==200,'Administrator can create unassigned jobs')
                rc,requester=sign_in(browser,url,'requester@example.test');requester.on('pageerror',lambda error:errors.append(str(error)))
                check(requester.locator('[data-action=nav][data-page=team]').count()==0,'Requester has no team controls')
                check('Private admin-only job' not in requester.locator('body').inner_text(),'Requester does not see unrelated jobs')
                requester.locator('.page-heading [data-action=new-job]').click()
                check(requester.locator('select[name=assignee_id]').count()==0 and requester.locator('select[name=status]').count()==0,'Requester form has no assignment or status controls')
                title='Chassis #614 - left light out'
                requester.locator('input[name=title]').fill(title);requester.locator('input[name=unit]').fill('Chassis #614')
                requester.locator('textarea[name=description]').fill('The left rear light is not working. Unit is in Bay 2.')
                requester.locator('select[name=priority]').select_option('High')
                requester.locator('input[type=file]').set_input_files(str(photo))
                requester.locator('button[form=job-form][type=submit]').click();wait_detail(requester,'New')
                check(requester.locator('#detail-status').is_disabled(),'Requester status is read-only')
                check(requester.locator('[data-action=edit-job]').count()==0,'Requester cannot edit job details')
                requester.locator('[data-action=upload-photos]').click()
                check(requester.locator('select[name=phase] option').all_text_contents()==['Before','General'],'Requester cannot label repair completion photos')
                requester.locator('[data-action=back-job]').click()
                requester.locator('[data-action=close-modal]').click()
                requester.screenshot(path=str(OUT/'three-roles-requester-desktop.png'),full_page=True)
                admin.locator('[data-action=nav][data-page=board]').click()
                admin.locator('.job-card').filter(has_text=title).click()
                admin.locator('[data-action=edit-job]').click()
                options=admin.locator('select[name=assignee_id] option').all_text_contents()
                check(options==['Unassigned','Carlos Technician'],'Only active technicians appear as assignees')
                admin.locator('select[name=assignee_id]').select_option(label='Carlos Technician')
                admin.locator('button[form=job-form][type=submit]').click();wait_detail(admin,'Assigned')
                check(admin.locator('.detail-info').inner_text().find('Demo Requester')>=0,'Admin sees original requester')
                tc,tech=sign_in(browser,url,'tech@example.test');tech.on('pageerror',lambda error:errors.append(str(error)))
                check(tech.locator('[data-action=new-job]').count()==0,'Technician cannot create jobs')
                check(tech.locator('[data-action=nav][data-page=team]').count()==0,'Technician cannot manage accounts')
                check(tech.locator('.job-card').count()==1,'Technician sees only assigned job')
                tech.locator('.job-card').filter(has_text=title).click()
                tech.locator('#detail-status').select_option('In Progress');wait_detail(tech,'In Progress')
                tech.locator('[data-action=upload-photos]').click()
                tech.locator('select[name=phase]').select_option('After')
                tech.locator('input[name=caption]').fill('Replacement lamp tested')
                tech.locator('input[type=file]').set_input_files(str(photo))
                tech.locator('button[form=photos-form][type=submit]').click()
                tech.locator('.photo-card').nth(1).wait_for()
                tech.locator('.comment-form textarea').fill('Replaced the lamp and checked the wiring.')
                tech.locator('.comment-form button[type=submit]').click()
                tech.locator('.timeline').get_by_text('Replaced the lamp and checked the wiring.').wait_for()
                tech.locator('#detail-status').select_option('Completed');wait_detail(tech,'Completed')
                tech.locator('[data-action=detail-tab][data-tab=photos]').click()
                tech.screenshot(path=str(OUT/'three-roles-technician-detail.png'),full_page=True)
                load_app(requester);requester.locator('.job-card').filter(has_text=title).click();wait_detail(requester,'Completed')
                check(requester.locator('.photo-card').count()==2,'Requester sees before and after photos')
                check(requester.locator('#detail-status').is_disabled(),'Completed request still read-only for requester')
                requester.locator('[data-action=detail-tab][data-tab=activity]').click()
                requester.locator('.timeline').get_by_text('Replaced the lamp and checked the wiring.').wait_for()
                check(True,'Requester sees technician completion notes')
                requester.set_viewport_size({'width':390,'height':844})
                check(requester.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Requester detail fits mobile viewport')
                requester.screenshot(path=str(OUT/'three-roles-requester-mobile.png'),full_page=True)
                requester.locator('[data-action=close-modal]').click()
                check(requester.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Requester dashboard fits mobile viewport')
                tech.set_viewport_size({'width':390,'height':844})
                check(tech.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Technician detail fits mobile viewport')
                check(not errors,'No real-app JavaScript runtime errors')
                # The independent local-only preview must implement the same visible flow.
                dc=browser.new_context(viewport={'width':1440,'height':1000});dc.set_default_timeout(8000);demo=dc.new_page()
                demo.on('pageerror',lambda error:errors.append(str(error)))
                load_demo(demo)
                check(demo.locator('[data-action=demo-switch]').count()==3,'Preview has all three role buttons')
                demo.locator('[data-action=demo-switch][data-role=requester]').click()
                demo.locator('.account small').filter(has_text='Requester').wait_for()
                check(demo.locator('.job-card').count()==4,'Preview requester sees only own sample requests')
                demo.locator('.page-heading [data-action=new-job]').click()
                demo.locator('input[name=title]').fill('Three-role preview request')
                demo.locator('button[form=job-form][type=submit]').click();wait_detail(demo,'New')
                demo.locator('[data-action=close-modal]').click()
                demo.locator('[data-action=demo-switch][data-role=admin]').click()
                demo.locator('.job-card').filter(has_text='Three-role preview request').click()
                demo.locator('[data-action=edit-job]').click()
                demo.locator('select[name=assignee_id]').select_option(label='Carlos M.')
                demo.locator('button[form=job-form][type=submit]').click();wait_detail(demo,'Assigned')
                demo.locator('[data-action=close-modal]').click()
                demo.locator('[data-action=demo-switch][data-role=technician]').click()
                demo.locator('.job-card').filter(has_text='Three-role preview request').click()
                demo.locator('#detail-status').select_option('Completed');wait_detail(demo,'Completed')
                demo.locator('[data-action=close-modal]').click()
                demo.locator('[data-action=demo-switch][data-role=requester]').click()
                demo.locator('.job-card').filter(has_text='Three-role preview request').click();wait_detail(demo,'Completed')
                check(demo.locator('#detail-status').is_disabled(),'Preview requester cannot change completion status')
                demo.locator('[data-action=close-modal]').click();load_demo(demo,preserve=True)
                demo.locator('.job-card').filter(has_text='Three-role preview request').wait_for()
                check(True,'Preview state survives a fresh document using a storage simulator')
                demo.set_viewport_size({'width':390,'height':844})
                check(demo.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Preview role controls fit mobile viewport')
                demo.screenshot(path=str(OUT/'three-roles-preview-mobile.png'),full_page=True)
                demo.set_viewport_size({'width':1440,'height':1000})
                demo.locator('[data-action=demo-switch][data-role=admin]').click()
                demo.screenshot(path=str(OUT/'three-roles-preview-admin.png'),full_page=True)
                check(not errors,'No preview JavaScript runtime errors')
                browser.close()
    text=f'{len(checks)} offline browser assertions passed.\nTransport: FastAPI TestClient bridge; localStorage simulator.\nNot a live HTTP, browser-cookie, or native localStorage test.\n'+'\n'.join('PASS: '+message for message in checks)+'\n'
    (OUT/'browser-three-roles-results.txt').write_text(text)
    print(text)

if __name__=='__main__':main()
