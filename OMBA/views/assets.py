#!/usr/bin/env python
# -*- coding=utf-8 -*-
import os, xlrd, time
from django.http import JsonResponse
from django.shortcuts import render, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from OMBA.models import *
from OMBA.utils.ansible_api_v2 import ANSRunner
from OMBA.tasks.assets import recordAssets
from OMBA.utils.logger import logger


def getBaseAssets():
    try:
        groupList = Group.objects.all()
    except:
        groupList = []
    try:
        serviceList = Server_Assets.objects.all()
    except:
        serviceList = []
    try:
        zoneList = Zone_Assets.objects.all()
    except:
        zoneList = []
    try:
        lineList = Line_Assets.objects.all()
    except:
        lineList = []
    try:
        raidList = Raid_Assets.objects.all()
    except:
        raidList = []
    try:
        projectList = Project_Assets.objects.all()
    except:
        projectList = []
    return {
        "group": groupList,
        "service": serviceList,
        "zone": zoneList,
        "line": lineList,
        "raid": raidList,
        "porject": projectList
    }


@login_required(login_url='/login')
@permission_required('OMBA.can_read_assets', login_url='/noperm/')
def assets_config(request):
    return render(
        request,
        'assets/assets_config.html',
        {
            "user": request.user,
            "baseAssets": getBaseAssets()
        }
    )


@login_required(login_url='/login')
@permission_required('OMBA.can_add_assets', login_url='/noperm/')
def assets_add(request):
    if request.method == "GET":
        userList = User.objects.all()
        return render(
            request,
            'assets/assets_add.html',
            {
                "user": request.user,
                "baseAssets": getBaseAssets(),
                "userList": userList
            }
        )


@login_required(login_url='/login')
@permission_required('OMBA.can_read_assets', login_url='/noperm/')
def assets_list(request):
    userList = User.objects.all()
    assetsList = Assets.objects.all().order_by("-id")
    for ds in assetsList:
        ds.nks = ds.networkcard_assets_set.all()
    assetOnline = Assets.objects.filter(status=0).count()
    assetOfflines = Assets.objects.filter(status=1).count()
    assetMaintain = Assets.objects.filter(status=2).count()
    assetsNumber = Assets.objects.values('assets_type').annotate(dcount=Count('assets_type'))
    return render(
        request,
        'assets_list.html',
        {
            "user": request.user,
            "totalAssets": assetsList.count(),
            "assetOnline": assetOnline,
            "assetOffline": assetOfflines,
            "assetMaintain": assetMaintain,
            "baseAssets": getBaseAssets(),
            "assetsList": assetsList,
            "assetsNumber": assetsNumber,
            "userList": userList
        }
    )


@login_required(login_url='/login')
@permission_required('OpsManage.can_read_assets', login_url='/noperm/')
def assets_view(request, aid):
    try:
        assets = Assets.objects.get(id=aid)
        userList = User.objects.all()
    except:
        return render(
            request,
            '404.html',
            {"user": request.user},
        )
    if assets.assets_type in ['server', 'vmser']:
        try:
            asset_ram = assets.ram_assets_set.all()
        except:
            asset_ram = []
        try:
            asset_disk = assets.disk_assets_set.all()
        except:
            asset_disk = []
        try:
            asset_nks = assets.networkcard_assets_set.all()
        except Exception, ex:
            asset_nks = []
            logger.warn(msg="获取网卡设备资产失败: {ex}".format(ex=str(ex)))
        try:
            asset_body = assets.server_assets
        except:
            return render(
                request,
                'assets/assets_view.html',
                {"user": request.user},
            )
        return render(
            request,
            'assets/assets_view.html',
            {
                "user": request.user,
                "asset_type": assets.assets_type,
                "asset_main": assets,
                "asset_body": asset_body,
                "asset_ram": asset_ram,
                "asset_disk": asset_disk,
                "baseAssets": getBaseAssets(),
                'userList': userList,
                "asset_nks": asset_nks
            },
        )
    else:
        try:
            asset_body = assets.network_assets
        except:
            return render(
                request,
                'assets/assets_view.html',
                {"user": request.user},
            )
        return render(
            request,
            'assets/assets_view.html',
            {
                "user": request.user,
                "asset_type": assets.assets_type,
                "asset_main": assets,
                "asset_body": asset_body,
                "baseAssets": getBaseAssets(),
                'userList': userList
            },
        )
