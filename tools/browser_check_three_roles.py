"""Optional Chromium smoke test. Uses disposable accounts and a temporary database."""
from pathlib import Path
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
OUT=ROOT/'docs'
TEMP='temporary-private-2026'
FINAL='final-browser-password-2026'
checks=[]

def check(value,message):
    assert value,message
    checks.append(message)

def wait_detail(page, state):
    page.locator('.detail-header .status-badge').filter(has_text=state).wait_for()

def sign_in(browser,url,email):
    context=browser.new_context(viewport={'width':1440,'height':1000})
    context.set_default_timeout(8000)
    page=context.new_page();page.goto(url)
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
    OUT.mkdir(exist_ok=True)
    errors=[]
    with tempfile.TemporaryDirectory(prefix='18w-role-browser-') as temp:
        data=Path(temp)/'data';photo=Path(temp)/'test-photo.jpg'
        Image.new('RGB',(120,80),(180,190,200)).save(photo)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        log=open(Path(temp)/'server.log','w')
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','app.server:create_app','--factory','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env={**os.environ,'EW_DATA_DIR':str(data)},stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url+'/health',timeout=1) as response:
                        if response.status==200:break
                except Exception:time.sleep(.1)
            else:raise RuntimeError('Test server did not start.')
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EW_BROWSER_PATH') or shutil.which('chromium'))
                browser.on('disconnected',lambda:None)
                admin_context=browser.new_context(viewport={'width':1440,'height':1000})
                admin_context.set_default_timeout(8000)
                admin=admin_context.new_page();admin.on('pageerror',lambda error:errors.append(str(error)))
                admin.goto(url+'/?setup_token='+(data/'.setup-token').read_text())
                admin.locator('input[name=name]').fill('Demo Admin')
                admin.locator('input[name=email]').fill('admin@example.test')
                admin.locator('input[name=password]').fill(FINAL)
                admin.locator('button[type=submit]').click()
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
                csrf=admin_context.request.get(url+'/api/session').json()['csrf']
                private=admin_context.request.post(url+'/api/jobs',headers={'x-csrf-token':csrf},data={'title':'Private admin-only job'})
                check(private.ok,'Administrator can create unassigned jobs')
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
                requester.reload();requester.locator('.job-card').filter(has_text=title).click();wait_detail(requester,'Completed')
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
                demo.goto((ROOT/'18wheelers-preview.html').as_uri())
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
                demo.locator('[data-action=close-modal]').click();demo.reload()
                demo.locator('.job-card').filter(has_text='Three-role preview request').wait_for()
                check(True,'Preview request survives page reload')
                demo.set_viewport_size({'width':390,'height':844})
                check(demo.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'Preview role controls fit mobile viewport')
                demo.screenshot(path=str(OUT/'three-roles-preview-mobile.png'),full_page=True)
                demo.set_viewport_size({'width':1440,'height':1000})
                demo.locator('[data-action=demo-switch][data-role=admin]').click()
                demo.screenshot(path=str(OUT/'three-roles-preview-admin.png'),full_page=True)
                check(not errors,'No preview JavaScript runtime errors')
                browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()
    text=f'{len(checks)} browser assertions passed.\n'+'\n'.join('PASS: '+message for message in checks)+'\n'
    (OUT/'browser-three-roles-results.txt').write_text(text)
    print(text)

if __name__=='__main__':main()
