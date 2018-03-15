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
@permission_required('OMBA.can_read_assets', login_url='/noperm/')
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


@login_required(login_url='/login')
@permission_required('OMBA.can_change_assets', login_url='/noperm/')
def assets_modf(request, aid):
    try:
        assets = Assets.objects.get(id=aid)
        userList = User.objects.all()
    except:
        return render(
            request,
            'assets/assets_modf.html',
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
            asset_body = assets.server_assets
        except Exception, ex:
            logger.error(msg="修改资产失败: {ex}".format(ex=str(ex)))
            return render(
                request,
                '404.html',
                {"user": request.user},
            )
        return render(
            request,
            'assets/assets_modf.html',
            {
                "user": request.user,
                "asset_type": assets.assets_type,
                "asset_main": assets,
                "asset_body": asset_body,
                "asset_ram": asset_ram,
                "asset_disk": asset_disk,
                "assets_data": getBaseAssets(),
                'userList': userList
            },
        )
    else:
        try:
            asset_body = assets.network_assets
        except:
            return render(
                request,
                'assets/assets_modf.html',
                {"user": request.user},
            )
        return render(
            request,
            'assets/assets_modf.html',
            {
                "user": request.user,
                "asset_type": assets.assets_type,
                "asset_main": assets,
                "asset_body": asset_body,
                "assets_data": getBaseAssets(),
                'userList': userList
            },
        )


@login_required(login_url='/login')
@permission_required('OMBA.can_change_server_assets', login_url='/noperm/')
def assets_facts(request, args=None):
    if request.method == "POST" and request.user.has_perm('OMBA.change_server_assets'):
        server_id = request.POST.get('server_id')
        genre = request.POST.get('type')
        if genre == 'setup':
            try:
                server_assets = Server_Assets.objects.get(id=request.POST.get('server_id'))
                if server_assets.keyfile == 1:
                    resource = [
                        {
                            "hostname": server_assets.ip,
                            "port": int(server_assets.port),
                            "username": server_assets.username
                        }
                    ]
                else:
                    resource = [
                        {
                            "hostname": server_assets.ip,
                            "port": server_assets.port,
                            "username": server_assets.username,
                            "password": server_assets.passwd
                        }
                    ]
            except Exception, ex:
                logger.error(msg="更新资产失败: {ex}".format(ex=str(ex)))
                return JsonResponse(
                    {
                        'msg': "数据更新失败-查询不到该主机资料",
                        "code": 502
                    }
                )
            ANS = ANSRunner(resource)
            ANS.run_model(
                host_list=[server_assets.ip],
                module_name='setup',
                module_args=""
            )
            data = ANS.handle_cmdb_data(ANS.get_model_result())
            if data:
                for ds in data:
                    status = ds.get('status')
                    if status == 0:
                        try:
                            assets = Assets.objects.get(id=server_assets.assets_id)
                            Assets.objects.filter(id=server_assets.assets_id).update(
                                sn=ds.get('serial'),
                                model=ds.get('model'),
                                manufacturer=ds.get('manufacturer')
                            )
                        except Exception, ex:
                            logger.error(msg="获取服务器信息失败: {ex}".format(ex=str(ex)))
                            return JsonResponse(
                                {
                                    'msg': "数据更新失败-查询不到该主机的资产信息",
                                    "code": 403
                                }
                            )
                        try:
                            Server_Assets.objects.filter(id=server_id).update(
                                cpu_number=ds.get('cpu_number'),
                                kernel=ds.get('kernel'),
                                selinux=ds.get('selinux'),
                                hostname=ds.get('hostname'),
                                system=ds.get('system'),
                                cpu=ds.get('cpu'),
                                disk_total=ds.get('disk_total'),
                                cpu_core=ds.get('cpu_core'),
                                swap=ds.get('swap'),
                                ram_total=ds.get('ram_total'),
                                vcpu_number=ds.get('vcpu_number')
                            )
                            recordAssets.delay(
                                user=str(request.user),
                                content="修改服务器资产：{ip}".format(ip=server_assets.ip),
                                type="server",
                                id=server_assets.id
                            )
                        except Exception, ex:
                            logger.error(msg="更新服务器信息失败: {ex}".format(ex=str(ex)))
                            return JsonResponse(
                                {
                                    'msg': "数据更新失败-写入数据失败",
                                    "code": 400
                                }
                            )
                        for nk in ds.get('nks'):
                            macaddress = nk.get('macaddress')
                            count = NetworkCard_Assets.objects.filter(assets=assets, macaddress=macaddress).count()
                            if count > 0:
                                try:
                                    NetworkCard_Assets.objects.filter(assets=assets, macaddress=macaddress).update(
                                        assets=assets,
                                        device=nk.get('device'),
                                        ip=nk.get('address'),
                                        module=nk.get('module'),
                                        mtu=nk.get('mtu'),
                                        active=nk.get('active')
                                    )
                                except Exception, ex:
                                    logger.warn(msg="更新服务器网卡信息失败: {ex}".format(ex=str(ex)))
                            else:
                                try:
                                    NetworkCard_Assets.objects.create(
                                        assets=assets,
                                        device=nk.get('device'),
                                        macaddress=nk.get('macaddress'),
                                        ip=nk.get('address'),
                                        module=nk.get('module'),
                                        mtu=nk.get('mtu'),
                                        active=nk.get('active')
                                    )
                                except Exception, ex:
                                    logger.warn(msg="写入服务器网卡信息失败: {ex}".format(ex=str(ex)))

                    else:
                        return JsonResponse(
                            {
                                'msg': "数据更新失败-无法链接主机",
                                "code": 502
                            }
                        )
                return JsonResponse(
                    {
                        'msg': "数据更新成功",
                        "code": 200
                    }
                )
            else:
                return JsonResponse(
                    {
                        'msg': "数据更新失败-请检查Ansible配置",
                        "code": 400
                    }
                )

        elif genre == 'crawHw':
            try:
                server_assets = Server_Assets.objects.get(id=server_id)
                assets = Assets.objects.get(id=server_assets.assets_id)
                if server_assets.keyfile == 1:
                    resource = [
                        {
                            "hostname": server_assets.ip,
                            "port": int(server_assets.port),
                            "username": server_assets.username
                        }
                    ]
                else:
                    resource = [
                        {
                            "hostname": server_assets.ip,
                            "port": server_assets.port,
                            "username": server_assets.username,
                            "password": server_assets.passwd
                        }
                    ]
            except Exception, ex:
                logger.error(msg="更新硬件信息失败: {ex}".format(ex=ex))
                return JsonResponse(
                    {
                        'msg': "数据更新失败-查询不到该主机资料",
                        "code": 502
                    }
                )
            ANS = ANSRunner(resource)
            ANS.run_model(
                host_list=[server_assets.ip],
                module_name='crawHw',
                module_args=""
            )
            data = ANS.handle_cmdb_crawHw_data(ANS.get_model_result())
            if data:
                for ds in data:
                    if ds.get('mem_info'):
                        for mem in ds.get('mem_info'):
                            if Ram_Assets.objects.filter(assets=assets, device_slot=mem.get('slot')).count() > 0:
                                try:
                                    Ram_Assets.objects.filter(assets=assets, device_slot=mem.get('slot')).update(
                                        device_slot=mem.get('slot'),
                                        device_model=mem.get('serial'),
                                        device_brand=mem.get('manufacturer'),
                                        device_volume=mem.get('size'),
                                        device_status="Online"
                                    )
                                except Exception, e:
                                    return JsonResponse(
                                        {
                                            'msg': "数据更新失败-写入数据失败",
                                            "code": 400
                                        }
                                    )
                            else:
                                try:
                                    Ram_Assets.objects.create(
                                        device_slot=mem.get('slot'),
                                        device_model=mem.get('serial'),
                                        device_brand=mem.get('manufacturer'),
                                        device_volume=mem.get('size'),
                                        device_status="Online",
                                        assets=assets
                                    )
                                    recordAssets.delay(
                                        user=str(request.user),
                                        content="修改服务器资产：{ip}".format(ip=server_assets.ip),
                                        type="server",
                                        id=server_assets.id
                                    )
                                except Exception, e:
                                    return JsonResponse(
                                        {
                                            'msg': "数据更新失败-写入数据失败",
                                            "code": 400
                                        }
                                    )
                    if ds.get('disk_info'):
                        for disk in ds.get('disk_info'):
                            if Disk_Assets.objects.filter(assets=assets, device_slot=disk.get('slot')).count() > 0:
                                try:
                                    Disk_Assets.objects.filter(assets=assets, device_slot=disk.get('slot')).update(
                                        device_serial=disk.get('serial'),
                                        device_model=disk.get('model'),
                                        device_brand=disk.get('manufacturer'),
                                        device_volume=disk.get('size'),
                                        device_status="Online"
                                    )
                                except Exception, e:
                                    return JsonResponse(
                                        {
                                            'msg': "数据更新失败-写入数据失败",
                                            "code": 400
                                        }
                                    )
                            else:
                                try:
                                    Disk_Assets.objects.create(
                                        device_serial=disk.get('serial'),
                                        device_model=disk.get('model'),
                                        device_brand=disk.get('manufacturer'),
                                        device_volume=disk.get('size'),
                                        device_status="Online",
                                        assets=assets,
                                        device_slot=disk.get('slot')
                                    )
                                    recordAssets.delay(
                                        user=str(request.user),
                                        content="修改服务器资产：{ip}".format(ip=server_assets.ip),
                                        type="server",
                                        id=server_assets.id
                                    )
                                except Exception, e:
                                    return JsonResponse(
                                        {
                                            'msg': "数据更新失败-写入数据失败",
                                            "code": 400
                                        }
                                    )
                return JsonResponse(
                    {
                        'msg': "数据更新成功",
                        "code": 200
                    }
                )
            else:
                return JsonResponse(
                    {
                        'msg': "数据更新失败，系统可能不支持，未能获取数据",
                        "code": 400
                    }
                )
    else:
        return JsonResponse(
            {
                'msg': "您没有该项操作的权限",
                "code": 400
            }
        )


@login_required(login_url='/login')
@permission_required('OpsManage.can_change_server_assets', login_url='/noperm/')
def assets_import(request):
    if request.method == "POST":
        f = request.FILES.get('import_file')
        filename = os.path.join(os.getcwd() + '/upload/', f.name)
        if os.path.isdir(os.path.dirname(filename)) is not True:
            os.makedirs(os.path.dirname(filename))
        fobj = open(filename, 'wb')
        for chrunk in f.chunks():
            fobj.write(chrunk)
        fobj.close()

        # 读取上传的execl文件内容方法
        def getAssetsData(fname=filename):
            bk = xlrd.open_workbook(fname)
            dataList = []
            try:
                server = bk.sheet_by_name("server")
                net = bk.sheet_by_name("net")
                for i in range(1, server.nrows):
                    dataList.append(server.row_values(i))
                for i in range(1, net.nrows):
                    dataList.append(net.row_values(i))
            except Exception, e:
                return []
            return dataList
        dataList = getAssetsData(fname=filename)
        # 获取服务器列表
        for data in dataList:
            assets = {
                'assets_type': data[0],
                'name': data[1],
                'sn': data[2],
                'buy_user': int(data[5]),
                'management_ip': data[6],
                'manufacturer': data[7],
                'model': data[8],
                'provider': data[9],
                'status': int(data[10]),
                'put_zone': int(data[11]),
                'group': int(data[12]),
                'project': int(data[13]),
                'business': int(data[14]),
            }
            if data[3]:
                assets['buy_time'] = xlrd.xldate.xldate_as_datetime(data[3], 0)
            if data[4]:
                assets['expire_date'] = xlrd.xldate.xldate_as_datetime(data[4], 0)
            if assets.get('assets_type') in ['vmser', 'server']:
                server_assets = {
                    'ip': data[15],
                    'keyfile': data[16],
                    'username': data[17],
                    'passwd': data[18],
                    'hostname': data[19],
                    'port': data[20],
                    'raid': data[21],
                    'line': data[22],
                }
            else:
                net_assets = {
                    'ip': data[15],
                    'bandwidth': data[16],
                    'port_number': data[17],
                    'firmware': data[18],
                    'cpu': data[19],
                    'stone': data[20],
                    'configure_detail': data[21]
                }
            count = Assets.objects.filter(name=assets.get('name')).count()
            if count == 1:
                assetsObj = Assets.objects.get(name=assets.get('name'))
                Assets.objects.filter(name=assets.get('name')).update(**assets)
                try:
                    if assets.get('assets_type') in ['vmser', 'server']:
                        Server_Assets.objects.filter(assets=assetsObj).update(**server_assets)
                    elif assets.get('assets_type') in ['switch', 'route', 'printer', 'scanner', 'firewall', 'storage', 'wifi']:
                        Network_Assets.objects.filter(assets=assetsObj).update(**net_assets)
                except Exception, ex:
                    print ex
            else:
                try:
                    assetsObj = Assets.objects.create(**assets)
                except Exception, ex:
                    logger.warn(msg="批量写入资产失败: {ex}".format(ex=str(ex)))
                if assetsObj:
                    try:
                        if assets.get('assets_type') in ['vmser', 'server']:
                            Server_Assets.objects.create(assets=assetsObj, **server_assets)
                        elif assets.get('assets_type') in ['switch', 'route', 'printer', 'scanner', 'firewall', 'storage', 'wifi']:
                            Network_Assets.objects.create(assets=assetsObj, **net_assets)
                    except Exception, ex:
                        logger.warn(msg="批量更新资产失败: {ex}".format(ex=str(ex)))
                        assetsObj.delete()
        return HttpResponseRedirect('/assets_list')
