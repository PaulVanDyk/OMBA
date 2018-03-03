#!/usr/bin/env python
# -*- coding=utf-8 -*-
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission


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
