#!/usr/bin/env python
# -*- coding=utf-8 -*-
import uuid, json
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from OMBA.models import (
    Project_Assets,
    Server_Assets,
    Project_Config,
    Project_Number,
    Project_Order,
    Log_Project_Config,
    Service_Assets,
    Assets
)
from OMBA.utils.git import GitTools
from OMBA.utils.svn import SvnTools
from OMBA.utils import base
from OMBA.data.DsRedisOps import DsRedis
from OMBA.utils.ansible_api_v2 import ANSRunner
from django.contrib.auth.models import User, Group
from OMBA.views.assets import getBaseAssets
from django.db.models import Count
from django.db.models import Q
from OMBA.tasks.deploy import recordProject, sendDeployNotice
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


@login_required()
@permission_required('OMBA.can_add_project_config', login_url='/noperm/')
def deploy_add(request):
    if request.method == "GET":
        serverList = Server_Assets.objects.all()
        groupList = Group.objects.all()
        return render(
            request,
            'deploy/deploy_add.html',
            {
                "user": request.user,
                "groupList": groupList,
                "serverList": serverList,
                'baseAssets': getBaseAssets()
            }
        )
    elif request.method == "POST":
        serverList = Server_Assets.objects.all()
        ipList = request.POST.getlist('server')
        try:
            proAssets = Project_Assets.objects.get(id=request.POST.get('project_id'))
        except Exception, ex:
            return render(
                request,
                'deploy/deploy_add.html',
                {
                    "user": request.user,
                    "errorInfo": "部署服务器信息添加错误：%s" % str(ex)
                },
            )
        try:
            project = Project_Config.objects.create(
                project=proAssets,
                project_service=request.POST.get('project_service'),
                project_env=request.POST.get('project_env'),
                project_repertory=request.POST.get('project_repertory'),
                project_address=request.POST.get('project_address'),
                project_repo_dir=request.POST.get('project_repo_dir'),
                project_remote_command=request.POST.get('project_remote_command'),
                project_local_command=request.POST.get('project_local_command'),
                project_dir=request.POST.get('project_dir'),
                project_uuid=uuid.uuid4(),
                project_exclude=request.POST.get('project_exclude', '.git').rstrip(),
                project_user=request.POST.get('project_user', 'root'),
                project_model=request.POST.get('project_model'),
                project_status=0,
                project_repo_user=request.POST.get('project_repo_user'),
                project_repo_passwd=request.POST.get('project_repo_passwd'),
                project_audit_group=request.POST.get('project_audit_group', None),
            )
            recordProject.delay(
                project_user=str(request.user),
                project_id=project.id,
                project_name=proAssets.project_name,
                project_content="添加项目"
            )
        except Exception, e:
            return render(
                request,
                'deploy/deploy_add.html',
                {
                    "user": request.user,
                    "serverList": serverList,
                    "errorInfo": "部署服务器信息添加错误：%s" % str(e)
                },
            )
        if ipList:
            for sid in ipList:
                try:
                    server = Server_Assets.objects.get(id=sid)
                    Project_Number.objects.create(
                        dir=request.POST.get('dir'),
                        server=server.ip,
                        project=project
                    )
                except Exception, e:
                    project.delete()
                    return render(
                        request,
                        'deploy/deploy_add.html',
                        {
                            "user": request.user,
                            "serverList": serverList,
                            "errorInfo": "目标服务器信息添加错误：%s" % str(e)
                        },
                    )
        return HttpResponseRedirect('/deploy_add')


@login_required()
@permission_required('OMBA.can_change_project_config', login_url='/noperm/')
def deploy_modf(request, pid):
    try:
        project = Project_Config.objects.select_related().get(id=pid)
        tagret_server = Project_Number.objects.filter(project=project)
        serverList = [s.server_assets for s in Assets.objects.filter(project=project.project.id)]
    except:
        return render(
            request,
            'deploy/deploy_modf.html',
            {
                "user": request.user,
                "errorInfo": "项目不存在，可能已经被删除."
            },
        )
    if request.method == "GET":
        serviceList = Service_Assets.objects.filter(project=project.project)
        groupList = Group.objects.all()
        server = [s.server for s in tagret_server]
        for ds in serverList:
            if ds.ip in server:
                ds.count = 1
            else:
                ds.count = 0
        return render(
            request,
            'deploy/deploy_modf.html',
            {
                "user": request.user,
                "project": project,
                "server": tagret_server,
                "serverList": serverList,
                "groupList": groupList,
                "serviceList": serviceList
            },
        )
    elif request.method == "POST":
        ipList = request.POST.getlist('server', None)
        try:
            Project_Config.objects.filter(id=pid).update(
                project_env=request.POST.get('project_env'),
                project_service=request.POST.get('project_service'),
                project_repertory=request.POST.get('project_repertory'),
                project_address=request.POST.get('project_address'),
                project_repo_dir=request.POST.get('project_repo_dir'),
                project_remote_command=request.POST.get('project_remote_command'),
                project_local_command=request.POST.get('project_local_command'),
                project_dir=request.POST.get('project_dir'),
                project_exclude=request.POST.get('project_exclude', '.git').rstrip(),
                project_user=request.POST.get('project_user'),
                project_audit_group=request.POST.get('project_audit_group'),
                project_repo_user=request.POST.get('project_repo_user'),
                project_repo_passwd=request.POST.get('project_repo_passwd'),
            )
            recordProject.delay(
                project_user=str(request.user),
                project_id=pid,
                project_name=project.project.project_name,
                project_content="修改项目"
            )
        except Exception, e:
            return render(
                request,
                'deploy/deploy_modf.html',
                {
                    "user": request.user,
                    "errorInfo": "更新失败：" + str(e)
                },
            )
        if ipList:
            tagret_server_list = [s.server for s in tagret_server]
            postServerList = []
            for sid in ipList:
                try:
                    server = Server_Assets.objects.get(id=sid)
                    postServerList.append(server.ip)
                    if server.ip not in tagret_server_list:
                        Project_Number.objects.create(
                            dir=request.POST.get('dir'),
                            server=server.ip,
                            project=project
                        )
                    elif server.ip in tagret_server_list and request.POST.get('dir'):
                        try:
                            Project_Number.objects.filter(
                                project=project,
                                server=server.ip
                            ).update(dir=request.POST.get('dir'))
                        except Exception, e:
                            print e
                            pass
                except Exception, e:
                    return render(
                        request,
                        'deploy/deploy_modf.html',
                        {
                            "user": request.user,
                            "serverList": serverList,
                            "errorInfo": "目标服务器信息添加错误：%s" % str(e)
                        },
                    )
            # 清除目标主机
            delList = list(set(tagret_server_list).difference(set(postServerList)))
            for ip in delList:
                Project_Number.objects.filter(project=project, server=ip).delete()
        return HttpResponseRedirect('/deploy_mod/{id}/'.format(id=pid))
