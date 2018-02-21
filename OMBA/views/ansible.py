#!/usr/bin/env python
# -*- coding=utf-8 -*-
import uuid
import os
import json
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from OMBA.models import Server_Assets
from OMBA.data.DsRedisOps import DsRedis
from OMBA.data.DsMySQL import AnsibleRecord
from OMBA.utils.ansible_api_v2 import ANSRunner
from django.contrib.auth.models import User, Group
from OMBA.models import (
    Ansible_Playbook,
    Ansible_Playbook_Number,
    Log_Ansible_Model,
    Log_Ansible_Playbook,
    Ansible_CallBack_Model_Result,
    Service_Assets,
    Ansible_CallBack_PlayBook_Result,
    Assets,
    Ansible_Script,
    Project_Assets
)


@login_required()
@permission_required('OMBA.can_read_ansible_model', login_url='/noperm/')
def apps_model(request):
    if request.method == "GET":
        projectList = Project_Assets.objects.all()
        serverList = Server_Assets.objects.all()
        groupList = Group.objects.all()
        serviceList = Service_Assets.objects.all()
        return render(
            request,
            'apps/apps_model.html',
            {
                "user": request.user,
                "ans_uuid": uuid.uuid4(),
                "serverList": serverList,
                "groupList": groupList,
                "serviceList": serviceList,
                "projectList": projectList
            }
        )
    elif request.method == "POST" and request.user.has_perm('OMBA.can_exec_ansible_model'):
        resource = []
        sList = []
        if request.POST.get('server_model') in ['service', 'group', 'custom']:
            if request.POST.get('server_model') == 'custom':
                serverList = request.POST.getlist('ansible_server')
                for server in serverList:
                    server_assets = Server_Assets.objects.get(id=server)
                    sList.append(server_assets.ip)
                    if server_assets.keyfile == 1:
                        resource.append(
                            {
                                "hostname": server_assets.ip,
                                "port": int(server_assets.port),
                                "username": server_assets.username
                            }
                        )
                    else:
                        resource.append(
                            {
                                "hostname": server_assets.ip,
                                "port": int(server_assets.port),
                                "username": server_assets.username,
                                "password": server_assets.passwd
                            }
                        )
            elif request.POST.get('server_model') == 'group':
                serverList = Assets.objects.filter(group=request.POST.get('ansible_group'))
                for server in serverList:
                    sList.append(server.server_assets.ip)
                    if server.server_assets.keyfile == 1:
                        resource.append(
                            {
                                "hostname": server.server_assets.ip,
                                "port": int(server.server_assets.port),
                                "username": server.server_assets.username
                            }
                        )
                    else:
                        resource.append(
                            {
                                "hostname": server.server_assets.ip,
                                "port": int(server.server_assets.port),
                                "username": server.server_assets.username,
                                "password": server.server_assets.passwd
                            }
                        )
            elif request.POST.get('server_model') == 'service':
                serverList = Assets.objects.filter(business=request.POST.get('ansible_service'))
                for server in serverList:
                    sList.append(server.server_assets.ip)
                    if server.server_assets.keyfile == 1:
                        resource.append(
                            {
                                "hostname": server.server_assets.ip,
                                "port": int(server.server_assets.port),
                                "username": server.server_assets.username
                            }
                        )
                    else:
                        resource.append(
                            {
                                "hostname": server.server_assets.ip,
                                "port": int(server.server_assets.port),
                                "username": server.server_assets.username,
                                "password": server.server_assets.passwd
                            }
                        )
            if len(request.POST.get('custom_model')) > 0:
                model_name = request.POST.get('custom_model')
            else:
                model_name = request.POST.get('ansible_model', None)
            if len(sList) > 0:
                redisKey = request.POST.get('ans_uuid')
                logId = AnsibleRecord.Model.insert(
                    user=str(request.user),
                    ans_model=model_name,
                    ans_server=','.join(sList),
                    ans_args=request.POST.get('ansible_args', None)
                )
                DsRedis.OpsAnsibleModel.delete(redisKey)
                DsRedis.OpsAnsibleModel.lpush(
                    redisKey,
                    "[Start] Ansible Model: {model}  ARGS:{args}".format(
                        model=model_name,
                        args=request.POST.get('ansible_args', "None")
                    )
                )
                if request.POST.get('ansible_debug') == 'on':
                    ANS = ANSRunner(resource, redisKey, logId, verbosity=4)
                else:
                    ANS = ANSRunner(resource, redisKey, logId)
                ANS.run_model(
                    host_list=sList,
                    module_name=model_name,
                    module_args=request.POST.get('ansible_args', "")
                )
                DsRedis.OpsAnsibleModel.lpush(redisKey, "[Done] Ansible Done.")
                return JsonResponse(
                    {
                        'msg': "操作成功",
                        "code": 200,
                        'data': []
                    }
                )
            else:
                return JsonResponse({'msg': "操作失败，未选择主机或者该分组没有成员", "code": 500, 'data': []})
        else:
            return JsonResponse({'msg': "操作失败，不支持的操作类型", "code": 500, 'data': []})

@login_required()
def ansible_run(request):
    if request.method == "POST":
        redisKey = request.POST.get('ans_uuid')
        msg = DsRedis.OpsAnsibleModel.rpop(redisKey)
        if msg:
            return JsonResponse(
                {
                    'msg': msg,
                    'code': 200,
                    'data': []
                }
            )
        else:
            return JsonResponse(
                {
                    'msg': None,
                    'code': 200,
                    'data': []
                }
            )

@login_required()
@permission_required('OMBA.can_add_ansible_playbook', login_url='/noperm/')
def app_upload(request):
    if request.method == "GET":
        serverList = Server_Assets.objects.all()
        projectList = Project_Assets.objects.all()
        groupList = Group.objects.all()
        userList = User.objects.all()
        serviceList = Service_Assets.objects.all()
        return render(
            request,
            'app/apps_playbook_upload.html',
            {
                "user": request.user,
                "userList": userList,
                "serverList": serverList,
                "groupList": groupList,
                "serviceList": serviceList,
                "projectList": projectList
            },
        )
    elif request.method == "POST":
        sList = []
        if request.POST.get('server_model') in ['service', 'group', 'custom']:
            if request.POST.get('server_model') == 'custom':
                for sid in request.POST.getlist('playbook_server'):
                    server = Service_Assets.objects.get(id=sid)
                    sList.append(server.ip)
                playbook_server_value = None
            elif request.POST.get('server_model') == 'group':
                serverList = Assets.objects.filter(group=request.POST.get('ansible_group'))
                sList = [s.server_assets.ip for s in serverList]
                playbook_server_value = request.POST.get('ansible_group')
            elif request.POST.get('server_model') == 'service':
                serverList = Assets.objects.filter(business=request.POST.get('ansible_service'))
                sList = [s.server_assets.ip for s in serverList]
                playbook_server_value = request.POST.get('ansible_service')
        try:
            playbook = Ansible_Playbook.objects.create(
                playbook_name=request.POST.get('playbook_name'),
                playbook_desc=request.POST.get('playbook_desc'),
                playbook_vars=request.POST.get('playbook_vars'),
                playbook_uuid=uuid.uuid4(),
                playbook_file=request.FILES.get('playbook_file'),
                playbook_server_model=request.POST.get('server_model', 'custom'),
                playbook_server_value=playbook_server_value,
                playbook_auth_group=request.POST.get('playbook_auth_group', 0),
                playbook_auth_user=request.POST.get('playbook_auth_user', 0),
                playbook_type=0,
            )
        except Exception, e:
            return render(
                request,
                'apps/apps_playbook_upload.html',
                {
                    "user": request.user,
                    "errorInfo": "剧本添加错误：%s" % str(e)
                },
            )
        for sip in sList:
            try:
                Ansible_Playbook_Number.objects.create(
                    playbook=playbook,
                    playbook_server=sip
                )
            except Exception, e:
                playbook.delete()
                return render(
                    request,
                    'apps/apps_playbook_upload.html',
                    {
                        "user": request.user,
                        "errorInfo": "目标服务器信息添加错误：%s" % str(e)
                    },
                )
        # 操作日志异步记录
        AnsibleRecord.PlayBook.insert(
            user=str(request.user),
            ans_id=playbook.id,
            ans_name=playbook.playbook_name,
            ans_content="添加Ansible剧本",
            ans_server=','.join(sList)
        )
        return HttpResponseRedirect('apps/playbook/upload/')


@login_required()
@permission_required('OpsManage.can_add_ansible_playbook', login_url='/noperm/')
def apps_online(request):
    if request.method == "GET":
        serverList = Server_Assets.objects.all()
        groupList = Group.objects.all()
        userList = User.objects.all()
        serviceList = Service_Assets.objects.all()
        projectList = Project_Assets.objects.all()
        return render(
            request,
            'apps/apps_playbook_online.html',
            {
                "user": request.user,
                "userList": userList,
                "serverList": serverList,
                "groupList": groupList,
                "serviceList": serviceList,
                "projectList": projectList
            },
        )
    elif request.method == "POST":
        sList = []
        playbook_server_value = None
        if request.POST.get('server_model') in ['service', 'group', 'custom']:
            if request.POST.get('server_model') == 'custom':
                for sid in request.POST.getlist('playbook_server[]'):
                    server = Server_Assets.objects.get(id=sid)
                    sList.append(server.ip)
                playbook_server_value = None
            elif request.POST.get('server_model') == 'group':
                serverList = Assets.objects.filter(group=request.POST.get('ansible_group'))
                sList = [s.server_assets.ip for s in serverList]
                playbook_server_value = request.POST.get('ansible_group')
            elif request.POST.get('server_model') == 'service':
                serverList = Assets.objects.filter(business=request.POST.get('ansible_service'))
                sList = [s.server_assets.ip for s in serverList]
                playbook_server_value = request.POST.get('ansible_service')
        fileName = '/upload/playbook/online-{ram}.yaml'.format(ram=uuid.uuid4().hex[0:8])
        filePath = os.getcwd() + fileName
        if request.POST.get('playbook_content'):
            if os.path.isdir(os.path.dirname(filePath)) is not True:
                os.makedirs(os.path.dirname(filePath))  # 判断文件存放的目录是否存在，不存在就创建
            with open(filePath, 'w') as f:
                f.write(request.POST.get('playbook_content'))
        else:
            return JsonResponse(
                {
                    'msg': "文件内容不能为空",
                    "code": 500,
                    'data': []
                }
            )
        try:
            playbook = Ansible_Playbook.objects.create(
                playbook_name=request.POST.get('playbook_name'),
                playbook_desc=request.POST.get('playbook_desc'),
                playbook_vars=request.POST.get('playbook_vars'),
                playbook_uuid=uuid.uuid4(),
                playbook_file=fileName,
                playbook_server_model=request.POST.get('server_model', 'custom'),
                playbook_server_value=playbook_server_value,
                playbook_auth_group=request.POST.get('playbook_auth_group', 0),
                playbook_auth_user=request.POST.get('playbook_auth_user', 0),
                playbook_type=1
            )
        except Exception, ex:
            return JsonResponse(
                {
                    'msg': str(ex),
                    "code": 500,
                    'data': []
                }
            )
        for sip in sList:
            try:
                Ansible_Playbook_Number.objects.create(
                    playbook=playbook,
                    playbook_server=sip
                )
            except Exception, ex:
                playbook.delete()
                print ex
        # 操作日志异步记录
        AnsibleRecord.PlayBook.insert(
            user=str(request.user),
            ans_id=playbook.id,
            ans_name=playbook.playbook_name,
            ans_content="添加Ansible剧本",
            ans_server=','.join(sList)
        )
        return JsonResponse(
            {
                'msg': None,
                "code": 200,
                'data': []
            }
        )
