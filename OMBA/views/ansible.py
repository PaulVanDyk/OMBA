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
                    "[Start] Ansible Model: {model}  ARGS:{args}".format(model=model_name, args=request.POST.get('ansible_args', "None")))
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
                return JsonResponse({'msg': "操作成功", "code": 200, 'data': []})
            else:
                return JsonResponse({'msg': "操作失败，未选择主机或者该分组没有成员", "code": 500, 'data': []})
        else:
            return JsonResponse({'msg': "操作失败，不支持的操作类型", "code": 500, 'data': []})