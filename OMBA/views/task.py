#!/usr/bin/env python
# -*- coding=utf-8 -*-
from django.http import JsonResponse
from django.shortcuts import render
from djcelery.models import PeriodicTask, CrontabSchedule, WorkerState, TaskState, IntervalSchedule
from django.contrib.auth.decorators import login_required
from celery.registry import tasks as cTasks
from celery.five import keys, items
from django.contrib.auth.decorators import permission_required


@login_required()
@permission_required('djcelery.change_periodictask', login_url='/noperm/')
def task_model(request):
    if request.method == "GET":
        # 获取注册的任务
        regTaskList = []
        for task in list(keys(cTasks)):
            if task.startswith('OpsManage.tasks.ansible') or task.startswith('OpsManage.tasks.sched'):
                regTaskList.append(task)
        try:
            crontabList = CrontabSchedule.objects.all().order_by("-id")
            intervalList = IntervalSchedule.objects.all().order_by("-id")
            taskList = PeriodicTask.objects.all().order_by("-id")
        except:
            crontabList = []
            intervalList = []
            taskList = []
        return render(
            request,
            'task/task_model.html',
            {
                "user": request.user,
                "crontabList": crontabList,
                "intervalList": intervalList,
                "taskList": taskList,
                "regTaskList": regTaskList
            }
        )
    elif request.method == "POST":
        op = request.POST.get('op')
        if op in [
            'addCrontab',
            'delCrontab',
            'addInterval',
            'delInterval',
            'addTask',
            'editTask',
            'delTask'
        ] and request.user.has_perm('djcelery.change_periodictask'):
            if op == 'addCrontab':
                try:
                    CrontabSchedule.objects.create(
                        minute=request.POST.get('minute'),
                        hour=request.POST.get('hour'),
                        day_of_week=request.POST.get('day_of_week'),
                        day_of_month=request.POST.get('day_of_month'),
                        month_of_year=request.POST.get('month_of_year'),
                    )
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "添加成功"
                        }
                    )
                except:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "添加失败"
                        }
                    )
            elif op == 'delCrontab':
                try:
                    CrontabSchedule.objects.get(id=request.POST.get('id')).delete()
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "删除成功"
                        }
                    )
                except:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "删除失败"
                        }
                    )
            elif op == 'addInterval':
                try:
                    IntervalSchedule.objects.create(
                        every=request.POST.get('every'),
                        period=request.POST.get('period')
                    )
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "添加成功"
                        }
                    )
                except:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "添加失败"
                        }
                    )
            elif op == 'delInterval':
                try:
                    IntervalSchedule.objects.get(id=request.POST.get('id')).delete()
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "删除成功"
                        }
                    )
                except:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "删除失败"
                        }
                    )
            elif op == 'addTask':
                try:
                    PeriodicTask.objects.create(
                        name=request.POST.get('name'),
                        interval_id=request.POST.get('interval', None),
                        task=request.POST.get('task', None),
                        crontab_id=request.POST.get('crontab', None),
                        args=request.POST.get('args', '[]'),
                        kwargs=request.POST.get('kwargs', '{}'),
                        queue=request.POST.get('queue', None),
                        enabled=int(request.POST.get('enabled', 1)),
                        expires=request.POST.get('expires', None)
                    )
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "添加成功"
                        }
                    )
                except Exception, e:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": str(e),
                            "msg": "添加失败"
                        }
                    )
            elif op == 'delTask':
                try:
                    PeriodicTask.objects.get(id=request.POST.get('id')).delete()
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "删除成功"
                        }
                    )
                except:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": None,
                            "msg": "删除失败"
                        }
                    )
            elif op == 'editTask':
                try:
                    task = PeriodicTask.objects.get(id=request.POST.get('id'))
                    task.name = request.POST.get('name')
                    task.interval_id = request.POST.get('interval', None)
                    task.crontab_id = request.POST.get('crontab', None)
                    task.args = request.POST.get('args')
                    task.kwargs = request.POST.get('kwargs')
                    task.queue = request.POST.get('queue', None)
                    task.expires = request.POST.get('expires', None)
                    task.enabled = int(request.POST.get('enabled'))
                    task.save()
                    return JsonResponse(
                        {
                            "code": 200,
                            "data": None,
                            "msg": "修改成功"
                        }
                    )
                except Exception, e:
                    return JsonResponse(
                        {
                            "code": 500,
                            "data": str(e),
                            "msg": "修改失败"
                        }
                    )
        else:
            return JsonResponse(
                {
                    "code": 500,
                    "data": None,
                    "msg": "不支持的操作或者您没有权限操作操作此项。"
                }
            )
    else:
        return JsonResponse(
            {
                "code": 500,
                "data": None,
                "msg": "不支持的HTTP操作"
            }
        )

