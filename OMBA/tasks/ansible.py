#!/usr/bin/env python
# -*- coding=utf-8 -*-
import os, json
from celery import task
from OMBA.data.DsMySQL import AnsibleRecord
from OMBA.utils.ansible_api_v2 import ANSRunner
from OMBA.models import (
    Ansible_Script,
    Ansible_Playbook,
    Server_Assets,
    Ansible_Playbook_Number
)


@task
def AnsibleScripts(**kw):
    logId = None
    resource = []
    try:
        if kw.has_key('scripts_id'):
            script = Ansible_Script.objects.get(id=kw.get('scripts_id'))
            filePath = os.getcwd() + str(script.script_file)
            if kw.has_key('hosts'):
                try:
                    sList = list(kw.get('hosts'))
                except Exception, ex:
                    return ex
            else:
                try:
                    sList = json.loads(script.script_server)
                except Exception, ex:
                    return ex
            if kw.has_key('logs'):
                logId = AnsibleRecord.Model.insert(
                    user='celery',
                    ans_model='script',
                    ans_server=','.join(sList),
                    ans_args=filePath
                )
            for sip in sList:
                try:
                    server_assets = Server_Assets.objects.get(ip=sip)
                except Exception, ex:
                    continue
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
            ANS = ANSRunner(resource, redisKey=None, logId=logId)
            ANS.run_model(host_list=sList, module_name='script', module_args=filePath)
            return ANS.get_model_result()
    except Exception, e:
        print e
        return False
