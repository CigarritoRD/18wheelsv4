"""Three-role permission, notification, and legacy-upgrade regression tests."""
import hashlib
import io
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.server import create_app, SCHEMA, password_hash, utcnow
from test_app import workspace, send, new_job, upload, image_bytes, employee_client, TEMP_PASSWORD

FINAL_PASSWORD='new-private-password-2026'


def requester_client(app, admin, email='requester@example.test'):
    result=send(admin,'POST','/api/users',{'name':'Requester','email':email,'password':TEMP_PASSWORD,'role':'requester'})
    assert result.status_code==200,result.text
    account=result.json()['user']
    client=TestClient(app)
    assert send(client,'POST','/api/login',{'email':email,'password':TEMP_PASSWORD}).status_code==200
    assert send(client,'POST','/api/password',{'current_password':TEMP_PASSWORD,'new_password':FINAL_PASSWORD}).status_code==200
    return client,account


def test_request_creation_is_unassigned_and_attributed(workspace):
    app,admin,_=workspace
    requester,account=requester_client(app,admin)
    job=new_job(requester,title='Broken chassis lamp',priority='High',due_date='2026-10-20')
    assert job['status']=='New' and job['assignee_id'] is None
    assert job['created_by']==account['id'] and job['created_by_name']=='Requester'
    assert job['completed_at'] is None and job['version']==1
    assert admin.get('/api/jobs').json()['jobs'][0]['id']==job['id']
    assert any(n['job_id']==job['id'] for n in admin.get('/api/notifications').json()['notifications'])


def test_requester_cannot_supply_privileged_creation_fields(workspace):
    app,admin,_=workspace;requester,_=requester_client(app,admin)
    for field,value in [('status','Completed'),('status','New'),('assignee_id',1),('assignee_id',None),('created_by',1),('id',999),('role','admin'),('archived',1),('version',99)]:
        response=send(requester,'POST','/api/jobs',{'title':'Tampered',field:value})
        assert response.status_code==403,(field,response.text)
    assert requester.get('/api/jobs').json()['jobs']==[]


def test_requester_isolation_for_jobs_photos_comments_and_history(workspace):
    app,admin,_=workspace;r1,_=requester_client(app,admin);r2,_=requester_client(app,admin,'another@example.test')
    own=new_job(r1);other=new_job(r2,title='Other request')
    assert upload(r1,own['id']).status_code==200
    photo=r1.get(f'/api/jobs/{own["id"]}').json()['photos'][0]
    assert [j['id'] for j in r1.get('/api/jobs').json()['jobs']]==[own['id']]
    assert r1.get(f'/api/jobs/{other["id"]}').status_code==404
    assert r2.get(photo['url']).status_code==404
    assert upload(r2,own['id']).status_code==404
    assert send(r2,'POST',f'/api/jobs/{own["id"]}/comments',{'body':'Intrusion'}).status_code==404
    assert r2.get(f'/api/jobs/{own["id"]}').status_code==404


def test_requester_admin_endpoints_and_status_are_forbidden(workspace):
    app,admin,_=workspace;r,account=requester_client(app,admin);job=new_job(r)
    assert upload(r,job['id']).status_code==200
    photo=r.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    attempts=[('GET','/api/users',None),('GET','/api/export',None),('POST','/api/users',{'role':'admin'}),('PATCH',f'/api/users/{account["id"]}',{'role':'admin'}),('PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':'Completed'}),('PATCH',f'/api/jobs/{job["id"]}',{'version':1,'title':'Changed'}),('POST',f'/api/jobs/{job["id"]}/archive',{'archived':True}),('DELETE',f'/api/photos/{photo["id"]}',None)]
    for method,path,body in attempts:
        result=send(r,method,path,body)
        assert result.status_code==403,(path,result.text)
    assert r.get(f'/api/jobs/{job["id"]}').json()['job']['status']=='New'


def test_only_active_technicians_can_be_assigned(workspace):
    app,admin,_=workspace;r,requester=requester_client(app,admin);tech,technician=employee_client(app,admin)
    job=new_job(r)
    for account_id in [1,requester['id']]:
        assert send(admin,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'assignee_id':account_id,'status':'Assigned'}).status_code==400
        assert send(admin,'POST','/api/jobs',{'title':'Wrong assignee','assignee_id':account_id}).status_code==400
    assert send(admin,'PATCH',f'/api/users/{technician["id"]}',{'active':False}).status_code==200
    assert send(admin,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'assignee_id':technician['id'],'status':'Assigned'}).status_code==400


def test_full_request_assign_complete_flow(workspace):
    app,admin,_=workspace;r,account=requester_client(app,admin);tech,technician=employee_client(app,admin)
    job=new_job(r,title='Replace chassis lamp');jid=job['id']
    assert upload(r,jid).status_code==200
    assert tech.get(f'/api/jobs/{jid}').status_code==404
    assigned=send(admin,'PATCH',f'/api/jobs/{jid}',{'version':1,'assignee_id':technician['id'],'status':'Assigned'})
    assert assigned.status_code==200,assigned.text
    assert tech.get(f'/api/jobs/{jid}').status_code==200
    assert send(tech,'PATCH',f'/api/jobs/{jid}',{'version':2,'status':'In Progress'}).status_code==200
    csrf=tech.get('/api/session').json()['csrf']
    result=tech.post(f'/api/jobs/{jid}/photos',headers={'x-csrf-token':csrf},data={'phase':'After'},files={'files':('after.jpg',image_bytes(),'image/jpeg')})
    assert result.status_code==200,result.text
    assert send(tech,'POST',f'/api/jobs/{jid}/comments',{'body':'Lamp replaced and tested.'}).status_code==200
    result=send(tech,'PATCH',f'/api/jobs/{jid}',{'version':3,'status':'Completed'})
    assert result.status_code==200,result.text
    detail=r.get(f'/api/jobs/{jid}').json()
    assert detail['job']['status']=='Completed' and detail['job']['completed_at']
    assert {p['phase'] for p in detail['photos']}=={'Before','After'}
    assert any(a['body']=='Lamp replaced and tested.' for a in detail['activity'])
    assert any('Completed' in n['body'] for n in r.get('/api/notifications').json()['notifications'])


def test_requester_phases_and_comments(workspace):
    app,admin,_=workspace;r,_=requester_client(app,admin);job=new_job(r)
    csrf=r.get('/api/session').json()['csrf']
    for phase,expected in [('Before',200),('General',200),('After',403)]:
        result=r.post(f'/api/jobs/{job["id"]}/photos',headers={'x-csrf-token':csrf},data={'phase':phase},files={'files':('photo.jpg',image_bytes(),'image/jpeg')})
        assert result.status_code==expected,result.text
    assert send(r,'POST',f'/api/jobs/{job["id"]}/comments',{'body':'The unit is now in Bay 2.'}).status_code==200
    assert any('commented' in n['body'] for n in admin.get('/api/notifications').json()['notifications'])
    assert len(r.get(f'/api/jobs/{job["id"]}').json()['photos'])==2


def test_technician_status_scope(workspace):
    app,admin,_=workspace;tech,account=employee_client(app,admin);job=new_job(admin,assignee_id=account['id'])
    for state in ['New','Assigned']:
        assert send(tech,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':state}).status_code==403
    for version,state in enumerate(['In Progress','On Hold','Completed'],start=1):
        assert send(tech,'PATCH',f'/api/jobs/{job["id"]}',{'version':version,'status':state}).status_code==200
    assert send(tech,'PATCH',f'/api/jobs/{job["id"]}',{'version':4,'assignee_id':None}).status_code==403


def test_archive_is_scoped_and_read_only_for_requester_and_technician(workspace):
    app,admin,_=workspace;r,_=requester_client(app,admin);other,_=requester_client(app,admin,'other@example.test');tech,account=employee_client(app,admin)
    job=new_job(r);jid=job['id']
    send(admin,'PATCH',f'/api/jobs/{jid}',{'version':1,'assignee_id':account['id'],'status':'Assigned'})
    send(admin,'POST',f'/api/jobs/{jid}/archive',{'archived':True})
    for client in [r,tech]:
        assert client.get('/api/jobs').json()['jobs']==[]
        assert [j['id'] for j in client.get('/api/jobs?archived=1').json()['jobs']]==[jid]
        assert client.get(f'/api/jobs/{jid}').status_code==200
        assert send(client,'POST',f'/api/jobs/{jid}/comments',{'body':'Blocked'}).status_code==400
        assert upload(client,jid).status_code==400
        assert send(client,'POST',f'/api/jobs/{jid}/archive',{'archived':False}).status_code==403
    assert other.get('/api/jobs?archived=1').json()['jobs']==[]
    assert other.get(f'/api/jobs/{jid}').status_code==404


def test_role_creation_and_least_privilege_default(workspace):
    _,admin,_=workspace
    for role in ['admin','technician','requester']:
        result=send(admin,'POST','/api/users',{'name':role,'email':f'{role}@example.test','password':TEMP_PASSWORD,'role':role})
        assert result.status_code==200,result.text
        assert result.json()['user']['role']==role
    default=send(admin,'POST','/api/users',{'name':'Default','email':'default@example.test','password':TEMP_PASSWORD})
    assert default.json()['user']['role']=='requester'
    for role in ['employee','superadmin','user','']:
        result=send(admin,'POST','/api/users',{'name':'Invalid','email':'invalid@example.test','password':TEMP_PASSWORD,'role':role})
        assert result.status_code==400


def test_reassignment_removes_technician_access_not_requester_access(workspace):
    app,admin,_=workspace;r,_=requester_client(app,admin);t1,a1=employee_client(app,admin);t2,a2=employee_client(app,admin,email='tech2@example.test')
    job=new_job(r);jid=job['id']
    send(admin,'PATCH',f'/api/jobs/{jid}',{'version':1,'assignee_id':a1['id'],'status':'Assigned'})
    upload(t1,jid);url=r.get(f'/api/jobs/{jid}').json()['photos'][0]['url']
    send(admin,'PATCH',f'/api/jobs/{jid}',{'version':2,'assignee_id':a2['id']})
    assert t1.get(f'/api/jobs/{jid}').status_code==404
    assert t1.get(url).status_code==404
    assert t1.get('/api/notifications').json()['notifications']==[]
    assert t2.get(url).status_code==200
    assert r.get(url).status_code==200


def test_changing_technician_role_requires_open_job_reassignment(workspace):
    app,admin,_=workspace;tech,account=employee_client(app,admin);job=new_job(admin,assignee_id=account['id'])
    for role in ['requester','admin']:
        assert send(admin,'PATCH',f'/api/users/{account["id"]}',{'role':role}).status_code==400
    send(tech,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':'Completed'})
    assert send(admin,'PATCH',f'/api/users/{account["id"]}',{'role':'requester'}).status_code==200
    assert tech.get('/api/jobs').status_code==401
    assert send(tech,'POST','/api/login',{'email':account['email'],'password':'employee-private-2026'}).status_code==200
    assert tech.get(f'/api/jobs/{job["id"]}').status_code==404
    assert tech.get('/api/notifications').json()['notifications']==[]


def test_requester_promoted_to_technician_sees_only_assigned_work(workspace):
    app,admin,_=workspace;r,account=requester_client(app,admin);job=new_job(r)
    assert send(admin,'PATCH',f'/api/users/{account["id"]}',{'role':'technician'}).status_code==200
    assert r.get('/api/jobs').status_code==401
    assert send(r,'POST','/api/login',{'email':account['email'],'password':FINAL_PASSWORD}).status_code==200
    assert r.get(f'/api/jobs/{job["id"]}').status_code==404
    assert r.get('/api/jobs').json()['jobs']==[]


def test_requester_notifications_do_not_leak_other_jobs(workspace):
    app,admin,_=workspace;r,account=requester_client(app,admin);own=new_job(r);other=new_job(admin)
    with app.state.db() as conn:
        conn.execute('INSERT INTO notifications(user_id,job_id,body,created_at) VALUES (?,?,?,?)',(account['id'],other['id'],'Private job notification',utcnow()))
    assert r.get('/api/notifications').json()['notifications']==[]


def make_legacy_database(path, corrupt=False):
    path.mkdir(exist_ok=True)
    database=path/'jobs.sqlite3'
    with sqlite3.connect(database) as conn:
        conn.executescript(SCHEMA.replace("CHECK(role IN ('admin','technician','requester'))","CHECK(role IN ('admin','employee'))"))
        for uid,role in [(1,'admin'),(2,'employee')]:
            conn.execute('INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES (?,?,?,?,?,?)',(uid,role,f'{role}@example.test',password_hash(TEMP_PASSWORD),role,utcnow()))
        conn.execute("INSERT INTO jobs(id,title,category,priority,status,assignee_id,created_by,created_at,updated_at) VALUES (1,'Existing job','Maintenance','Normal','Assigned',2,?,?,?)",(999 if corrupt else 1,utcnow(),utcnow()))
        conn.execute("INSERT INTO activity(job_id,user_id,kind,body,created_at) VALUES (1,2,'comment','Keep history',?)",(utcnow(),))
        conn.execute("INSERT INTO photos(job_id,filename,original_name,phase,uploaded_by,created_at) VALUES (1,'kept.jpg','original.jpg','Before',2,?)",(utcnow(),))
        conn.execute("INSERT INTO notifications(user_id,job_id,body,created_at) VALUES (2,1,'Keep notification',?)",(utcnow(),))
        conn.execute("INSERT INTO sessions VALUES ('old-token',2,'csrf',9999999999)")
    (path/'uploads').mkdir(exist_ok=True)
    (path/'uploads/kept.jpg').write_bytes(image_bytes())
    return database


def test_legacy_migration_preserves_data_and_is_idempotent(tmp_path):
    db=make_legacy_database(tmp_path)
    old_photo=(tmp_path/'uploads/kept.jpg').read_bytes()
    app=create_app(tmp_path)
    with app.state.db() as conn:
        assert conn.execute('SELECT role FROM users WHERE id=2').fetchone()[0]=='technician'
        assert conn.execute('SELECT assignee_id,created_by FROM jobs WHERE id=1').fetchone()[:]==(2,1)
        assert conn.execute('SELECT body FROM activity').fetchone()[0]=='Keep history'
        assert conn.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert conn.execute('PRAGMA user_version').fetchone()[0]==2
        for table in ['photos','notifications','jobs']:
            assert conn.execute('SELECT count(*) FROM '+table).fetchone()[0]==1
    assert (tmp_path/'uploads/kept.jpg').read_bytes()==old_photo
    backups=list(tmp_path.glob('jobs-before-three-roles-*.sqlite3'))
    assert len(backups)==1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute('SELECT role FROM users WHERE id=2').fetchone()[0]=='employee'
    create_app(tmp_path)
    assert len(list(tmp_path.glob('jobs-before-three-roles-*.sqlite3')))==1
    admin=TestClient(app)
    assert send(admin,'POST','/api/login',{'email':'admin@example.test','password':TEMP_PASSWORD}).status_code==200
    result=send(admin,'POST','/api/users',{'name':'New requester','email':'new@example.test','password':TEMP_PASSWORD,'role':'requester'})
    assert result.status_code==200,result.text
    assert result.json()['user']['id']>2


def test_legacy_migration_rolls_back_on_broken_references(tmp_path):
    db=make_legacy_database(tmp_path,corrupt=True)
    with pytest.raises(RuntimeError,match='integrity check'):
        create_app(tmp_path)
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT role FROM users WHERE id=2').fetchone()[0]=='employee'
        assert conn.execute('SELECT count(*) FROM sessions').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM jobs').fetchone()[0]==1


def test_backup_does_not_trigger_role_migration(tmp_path):
    import os
    import subprocess
    import sys
    import zipfile
    from pathlib import Path
    store=tmp_path/'original'
    db=make_legacy_database(store)
    output=tmp_path/'backups'
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'admin.py'),'backup','--server-stopped','--output',str(output)],env={**os.environ,'EW_DATA_DIR':str(store)},capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT role FROM users WHERE id=2').fetchone()[0]=='employee'
    assert not list(store.glob('jobs-before-three-roles-*'))
    archive=next(output.glob('*.zip'))
    with zipfile.ZipFile(archive) as z:
        assert z.read('data/uploads/kept.jpg')==(store/'uploads/kept.jpg').read_bytes()
        backup_db=tmp_path/'backup.sqlite3'
        backup_db.write_bytes(z.read('data/jobs.sqlite3'))
    with sqlite3.connect(backup_db) as conn:
        assert conn.execute('SELECT role FROM users WHERE id=2').fetchone()[0]=='employee'
