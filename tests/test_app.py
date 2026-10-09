import io
import sqlite3
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.server import create_app

ADMIN_PASSWORD='manager-private-2026'
TEMP_PASSWORD='temporary-private-2026'
EMPLOYEE_PASSWORD='employee-private-2026'


def send(client,method,path,body=None,**kwargs):
    csrf=client.get('/api/session').json()['csrf']
    return client.request(method,path,json=body,headers={'x-csrf-token':csrf},**kwargs)


@pytest.fixture
def workspace(tmp_path):
    app=create_app(tmp_path)
    client=TestClient(app)
    token=(tmp_path/'.setup-token').read_text()
    result=send(client,'POST','/api/setup',{'name':'Manager','email':'manager@example.test','password':ADMIN_PASSWORD,'setup_token':token})
    assert result.status_code==200,result.text
    return app,client,tmp_path


def add_employee(client,name='Carlos',email='carlos@example.test'):
    result=send(client,'POST','/api/users',{'name':name,'email':email,'password':TEMP_PASSWORD,'role':'technician'})
    assert result.status_code==200,result.text
    return result.json()['user']


def employee_client(app,manager,email='carlos@example.test'):
    account=add_employee(manager,email=email)
    employee=TestClient(app)
    result=send(employee,'POST','/api/login',{'email':email,'password':TEMP_PASSWORD})
    assert result.status_code==200,result.text
    result=send(employee,'POST','/api/password',{'current_password':TEMP_PASSWORD,'new_password':EMPLOYEE_PASSWORD})
    assert result.status_code==200,result.text
    return employee,account


def new_job(client,**changes):
    data={'title':'Inspect truck','unit':'VNR #125','category':'Maintenance','priority':'Normal','description':'Check and document the work.'}
    data.update(changes)
    response=send(client,'POST','/api/jobs',data)
    assert response.status_code==200,response.text
    return response.json()['job']


def image_bytes():
    buffer=io.BytesIO()
    image=Image.new('RGB',(120,80),'navy')
    exif=image.getexif();exif[0x010E]='sensitive test metadata'
    image.save(buffer,'JPEG',exif=exif)
    return buffer.getvalue()


def upload(client,job_id,content=None,name='image.jpg'):
    csrf=client.get('/api/session').json()['csrf']
    return client.post(f'/api/jobs/{job_id}/photos',headers={'x-csrf-token':csrf},data={'phase':'Before','caption':'Reference'},files={'files':(name,content if content is not None else image_bytes(),'image/jpeg')})


def test_health_and_public_index(workspace):
    app,_,_=workspace
    anonymous=TestClient(app)
    assert anonymous.get('/health').json()=={'status':'ok'}
    assert anonymous.get('/').status_code==200
    assert anonymous.get('/api/jobs').status_code==401


def test_setup_token_and_one_time_setup(tmp_path):
    app=create_app(tmp_path);client=TestClient(app)
    assert client.get('/api/session').json()['needs_setup']
    data={'name':'Manager','email':'manager@example.test','password':ADMIN_PASSWORD,'setup_token':'wrong'}
    assert send(client,'POST','/api/setup',data).status_code==403
    data['setup_token']=(tmp_path/'.setup-token').read_text()
    assert send(client,'POST','/api/setup',data).status_code==200
    assert send(client,'POST','/api/setup',data).status_code==409


def test_csrf_required(workspace):
    _,client,_=workspace
    assert client.post('/api/jobs',json={'title':'No csrf'}).status_code==403
    assert client.post('/api/logout').status_code==403


def test_session_rotation_and_logout(workspace):
    app,client,_=workspace
    old=client.cookies.get('ew_session')
    send(client,'POST','/api/logout')
    assert client.get('/api/jobs').status_code==401
    response=send(client,'POST','/api/login',{'email':'manager@example.test','password':ADMIN_PASSWORD})
    assert response.status_code==200
    assert client.cookies.get('ew_session')!=old
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']


def test_first_login_requires_password_change(workspace):
    app,manager,_=workspace;add_employee(manager)
    employee=TestClient(app)
    response=send(employee,'POST','/api/login',{'email':'carlos@example.test','password':TEMP_PASSWORD})
    assert response.json()['user']['must_change']==1
    assert employee.get('/api/jobs').status_code==403
    assert send(employee,'POST','/api/password',{'current_password':TEMP_PASSWORD,'new_password':EMPLOYEE_PASSWORD}).status_code==200
    assert employee.get('/api/jobs').status_code==200


def test_password_whitespace_preserved(workspace):
    app,client,_=workspace
    password='  deliberately spaced password  '
    assert send(client,'POST','/api/password',{'current_password':ADMIN_PASSWORD,'new_password':password}).status_code==200
    send(client,'POST','/api/logout')
    assert send(client,'POST','/api/login',{'email':'manager@example.test','password':password}).status_code==200


def test_employee_cannot_manage_accounts_or_jobs(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    assert employee.get('/api/users').status_code==403
    assert send(employee,'POST','/api/jobs',{'title':'Forbidden'}).status_code==403
    assert send(employee,'POST','/api/users',{'name':'Fake'}).status_code==403
    assert employee.get('/api/export').status_code==403


def test_employee_sees_only_own_jobs(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    own=new_job(manager,assignee_id=account['id'])
    other=new_job(manager,title='Private manager job')
    assert [j['id'] for j in employee.get('/api/jobs').json()['jobs']]==[own['id']]
    assert employee.get(f'/api/jobs/{other["id"]}').status_code==404
    assert send(employee,'PATCH',f'/api/jobs/{other["id"]}',{'version':1,'status':'Completed'}).status_code==404


def test_employee_updates_status_but_not_assignment(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    job=new_job(manager,assignee_id=account['id'])
    result=send(employee,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':'In Progress'})
    assert result.status_code==200,result.text
    assert result.json()['job']['status']=='In Progress'
    result=send(employee,'PATCH',f'/api/jobs/{job["id"]}',{'version':2,'title':'Changed'})
    assert result.status_code==403


def test_concurrent_edit_detected(workspace):
    _,client,_=workspace;job=new_job(client)
    assert send(client,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'title':'New title'}).status_code==200
    assert send(client,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'title':'Lost update'}).status_code==409


def test_completed_timestamp_and_reopening(workspace):
    _,client,_=workspace;job=new_job(client)
    done=send(client,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':'Completed'}).json()['job']
    assert done['completed_at']
    reopened=send(client,'PATCH',f'/api/jobs/{job["id"]}',{'version':2,'status':'New'}).json()['job']
    assert reopened['completed_at'] is None


def test_bad_job_validation(workspace):
    _,client,_=workspace
    for data in [{'title':''},{'title':'x','due_date':'2026-02-30'},{'title':'x','status':'Assigned'},{'title':'x','priority':'Extreme'},{'title':'x','assignee_id':9999}]:
        assert send(client,'POST','/api/jobs',data).status_code==400


def test_photos_authorization_and_metadata_removal(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    other,other_account=employee_client(app,manager,email='other@example.test')
    job=new_job(manager,assignee_id=account['id'])
    response=upload(employee,job['id']);assert response.status_code==200,response.text
    detail=manager.get(f'/api/jobs/{job["id"]}').json()
    assert detail['job']['photo_count']==1
    url=detail['photos'][0]['url']
    assert TestClient(app).get(url).status_code==401
    assert other.get(url).status_code==404
    received=employee.get(url)
    assert received.status_code==200
    assert not Image.open(io.BytesIO(received.content)).getexif()
    assert upload(other,job['id']).status_code==404


def test_external_photo_store_keeps_objects_private(tmp_path):
    class MemoryPhotoStore:
        kind='memory'
        def __init__(self):self.objects={}
        def put(self,key,content):self.objects[key]=content
        def get(self,key):return self.objects.get(key)
        def delete(self,key):self.objects.pop(key,None)

    store=MemoryPhotoStore()
    app=create_app(tmp_path,photo_store=store)
    client=TestClient(app)
    token=(tmp_path/'.setup-token').read_text()
    result=send(client,'POST','/api/setup',{'name':'Manager','email':'manager@example.test','password':ADMIN_PASSWORD,'setup_token':token})
    assert result.status_code==200,result.text
    job=new_job(client)
    assert upload(client,job['id']).status_code==200
    photo=client.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    assert len(store.objects)==1 and next(iter(store.objects)).endswith('.jpg')
    assert not list((tmp_path/'uploads').iterdir())
    assert TestClient(app).get(photo['url']).status_code==401
    assert client.get(photo['url']).status_code==200
    assert send(client,'DELETE',f'/api/photos/{photo["id"]}').status_code==200
    assert store.objects=={}


def test_fake_image_rejected_atomically(workspace):
    _,client,_=workspace;job=new_job(client)
    assert upload(client,job['id'],b'<svg onload="evil()"></svg>','x.jpg').status_code==400
    assert client.get(f'/api/jobs/{job["id"]}').json()['photos']==[]


def test_upload_batch_is_atomic(workspace):
    _,client,_=workspace;job=new_job(client)
    csrf=client.get('/api/session').json()['csrf']
    response=client.post(f'/api/jobs/{job["id"]}/photos',headers={'x-csrf-token':csrf},data={'phase':'Before'},files=[('files',('valid.jpg',image_bytes(),'image/jpeg')),('files',('bad.jpg',b'bad','image/jpeg'))])
    assert response.status_code==400
    assert client.get(f'/api/jobs/{job["id"]}').json()['photos']==[]


def test_large_photo_rejected(workspace):
    _,client,_=workspace;job=new_job(client)
    assert upload(client,job['id'],b'x'*(12*1024*1024+1)).status_code==400


def test_request_size_limit(workspace):
    _,client,_=workspace
    response=client.post('/api/jobs',content=b'',headers={'Content-Length':str(40*1024*1024)})
    assert response.status_code==413


def test_only_manager_can_delete_photos(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager);job=new_job(manager,assignee_id=account['id'])
    assert upload(employee,job['id']).status_code==200
    photo=manager.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    assert send(employee,'DELETE','/api/photos/'+str(photo['id'])).status_code==403
    assert send(manager,'DELETE','/api/photos/'+str(photo['id'])).status_code==200
    assert manager.get(photo['url']).status_code==404


def test_comments_and_history(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager);job=new_job(manager,assignee_id=account['id'])
    assert send(employee,'POST',f'/api/jobs/{job["id"]}/comments',{'body':'Work complete <script>alert(1)</script>'}).status_code==200
    detail=manager.get(f'/api/jobs/{job["id"]}').json()
    assert detail['job']['comment_count']==1
    assert detail['activity'][0]['kind']=='comment'


def test_archive_restore_preserves_history(workspace):
    _,manager,_=workspace;job=new_job(manager)
    assert send(manager,'POST',f'/api/jobs/{job["id"]}/archive',{'archived':True}).status_code==200
    assert manager.get('/api/jobs').json()['jobs']==[]
    assert len(manager.get('/api/jobs?archived=1').json()['jobs'])==1
    assert send(manager,'POST',f'/api/jobs/{job["id"]}/comments',{'body':'Not allowed'}).status_code==400
    assert send(manager,'POST',f'/api/jobs/{job["id"]}/archive',{'archived':False}).status_code==200
    assert len(manager.get('/api/jobs').json()['jobs'])==1
    assert len(manager.get(f'/api/jobs/{job["id"]}').json()['activity'])==3


def test_deactivation_requires_reassignment_and_revokes_session(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    job=new_job(manager,assignee_id=account['id'])
    assert send(manager,'PATCH',f'/api/users/{account["id"]}',{'active':False}).status_code==400
    send(manager,'PATCH',f'/api/jobs/{job["id"]}',{'version':1,'status':'New','assignee_id':None})
    assert send(manager,'PATCH',f'/api/users/{account["id"]}',{'active':False}).status_code==200
    assert employee.get('/api/jobs').status_code==401


def test_admin_cannot_lock_self_out(workspace):
    _,client,_=workspace
    assert send(client,'PATCH','/api/users/1',{'active':False}).status_code==400
    assert send(client,'PATCH','/api/users/1',{'role':'technician'}).status_code==400


def test_password_reset_revokes_sessions(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    response=send(manager,'PATCH',f'/api/users/{account["id"]}',{'password':'replacement-temporary-2026'})
    assert response.status_code==200
    assert employee.get('/api/jobs').status_code==401


def test_notification_assignment_and_seen(workspace):
    app,manager,_=workspace;employee,account=employee_client(app,manager)
    job=new_job(manager,assignee_id=account['id'])
    notifications=employee.get('/api/notifications').json()['notifications']
    assert notifications and notifications[0]['job_id']==job['id'] and not notifications[0]['seen']
    send(employee,'POST','/api/notifications/read')
    assert employee.get('/api/notifications').json()['notifications'][0]['seen']==1


def test_csv_formula_injection_protection(workspace):
    _,client,_=workspace;new_job(client,title='=HYPERLINK("bad")')
    response=client.get('/api/export')
    assert response.status_code==200
    assert "'=HYPERLINK" in response.text
    assert 'attachment' in response.headers['content-disposition']


def test_data_survives_new_app_instance(workspace):
    _,client,path=workspace;job=new_job(client,title='Persistent job')
    app2=create_app(path);client2=TestClient(app2)
    assert send(client2,'POST','/api/login',{'email':'manager@example.test','password':ADMIN_PASSWORD}).status_code==200
    assert client2.get('/api/jobs').json()['jobs'][0]['title']=='Persistent job'


def test_security_headers_and_private_storage(workspace):
    _,client,_=workspace
    response=client.get('/')
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['x-frame-options']=='DENY'
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert client.get('/data/jobs.sqlite3').status_code==404
    assert client.get('/api/users').headers['cache-control']=='no-store'


def test_login_rate_limited(workspace):
    app,_,_=workspace;client=TestClient(app)
    for _ in range(10):
        assert send(client,'POST','/api/login',{'email':'manager@example.test','password':'bad'}).status_code==401
    assert send(client,'POST','/api/login',{'email':'manager@example.test','password':'bad'}).status_code==429
