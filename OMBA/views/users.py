#!/usr/bin/env python
# -*- coding=utf-8 -*-
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.db.models import Q
from OMBA.views import assets
from OMBA.models import (
    Server_Assets,
    Project_Order,
    Service_Assets,
    Assets,
    User_Server,
    Global_Config,
    Project_Assets
)


@login_required()
@permission_required('auth.change_user', login_url='/noperm/')
def user_manage(request):
    if request.method == "GET":
        userList = User.objects.all()
        groupList = Group.objects.all()
        return render(
            request,
            'users/user_manage.html',
            {
                "user": request.user,
                "userList": userList,
                "groupList": groupList
            }
        )


def register(request):
    if request.method == "POST":
        if request.POST.get('password') == request.POST.get('c_password'):
            try:
                user = User.objects.filter(username=request.POST.get('username'))
                if len(user) > 0:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "注册失败，用户已存在。"
                        }
                    )
                else:
                    user = User()
                    user.username = request.POST.get('username')
                    user.email = request.POST.get('email')
                    user.set_password(request.POST.get('password'))
                    user.is_staff = 0
                    user.is_active = 0
                    user.is_superuser = 0
                    user.save()
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "用户注册成功"
                        }
                    )
            except Exception, e:
                return JsonResponse(
                    {
                        "code": 500,
                        "data": None,
                        "msg": "用户注册失败"
                    }
                )
        else:
            return JsonResponse(
                {
                    "code": 500,
                    "data": None,
                    "msg": "用户注册失败：两次输入的密码不一致"
                }
            )

@login_required()
def user_center(request):
    if request.method == "GET":
        serverList = []
        baseAssets = {}
        try:
            baseAssets = assets.getBaseAssets()
            config = Global_Config.objects.get(id=1)
            if config.webssh == 1 and request.user.is_superuser:
                serverList = Assets.objects.all().order_by("-id")
            elif config.webssh == 1:
                userServer = User_Server.objects.filter(user_id=int(request.user.id))
                serverList = []
                for s in userServer:
                    ser = Service_Assets.objects.get(id=s.server_id)
                    serverList.append(ser.assets)
        except:
            config = None
        orderList = Project_Order.objects.filter(Q(order_user=User.objects.get(username=request.user)) | Q(order_audit=User.objects.get(username=request.user))).order_by("id")[0:150]
        return render(
            request,
            'users/user_center.html',
            {
                "user": request.user,
                "orderList": orderList,
                "serverList": serverList,
                "baseAssets": baseAssets,
                "config": config
            }
        )
    if request.method == "POST":
        if request.POST.get("password") == request.POST.get("c_password"):
            try:
                user = User.objects.get(username=request.user)
                user.set_password(request.POST.get('password'))
                user.save()
                return JsonResponse(
                    {
                        "code": 200,
                        "data": None,
                        "msg": "密码修改成功"
                    }
                )
            except Exception, e:
                return JsonResponse(
                    {
                        "code": 500,
                        "data": None,
                        "msg": "密码修改失败：%s" % str(e)
                    }
                )
        else:
            return JsonResponse(
                {
                    "code": 500,
                    "data": None,
                    "msg": "密码修改失败：两次输入的密码不一致"
                }
            )

@login_required
@permission_required('auth.change_user', login_url='/noperm/')
def user(request, uid):
    if request.method == "GET":
        try:
            user = User.objects.get(id=uid)
        except Exception, e:
            return render(
                request,
                'users/user_info.html',
                {
                    "user": request.user,
                    "errorInfo": "用户不存在"
                }
            )
        # 获取用户权限列表