#!/usr/bin/env python
# -*- coding=utf-8 -*-

import json
import re
from collections import namedtuple
from ansible import constants
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory, Host, Group
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from OMBA.data.DsRedisOps import DsRedis
from OMBA.data.DsMySQL import AnsibleSaveResult


class MyInventory(Inventory):
    """
    this is my ansible inventory object.
    """
    def __init__(self, resource, loader, variable_manager):
        """
        ansible inventory object
        :param resource: 一个列表字典，如
            {
                "group1": {
                    "hosts": [{"hostname": "10.0.0.0", "port": "22", "username": "test", "password": "pass"}, ...],
                    "vars": {"var1": value1, "var2": value2, ...}
                }
            }
            如果只传入1个列表，这默认该列表内的所有主机属于 my_group 组,比如
            [{"hostname": "10.0.0.0", "port": "22", "username": "test", "password": "pass"}, ...]
        :param loader:
        :param variable_manager:
        """
        self.resource = resource
        self.inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=[])
        self.dynamic_inventory()

    def add_dynamic_group(self, hosts, groupname, groupvars=None):
        """
        add hosts to a group
        :param hosts:
        :param groupname:
        :param groupvars:
        :return:
        """
        my_group = Group(name=groupname)

        # if group variables exists, add them to group
        if groupvars:
            for key, value in groupvars.iteritems():
                my_group.set_variable(key, value)

        # add hosts to group
        for host in hosts:
            # set connection variables
            hostname = host.get("hostname")
            hostip = host.get('ip', hostname)
            hostport = host.get("port")
            username = host.get("username")
            password = host.get("password")
            if username == 'root':
                keyfile = "/root/.ssh/id_rsa"
            else:
                keyfile = "/home/{user}/.ssh/id_rsa".format(user=username)
            ssh_key = host.get("ssh_key", keyfile)
            my_host = Host(name=hostname, port=hostport)
            my_host.set_variable('ansible_ssh_host', hostip)
            my_host.set_variable('ansible_ssh_port', hostport)
            my_host.set_variable('ansible_ssh_user', username)
            my_host.set_variable('ansible_ssh_pass', password)
            my_host.set_variable('ansible_ssh_private_key_file', ssh_key)

            # set other variables
            for key, value in host.iteritems():
                if key not in ["hostname", "port", "username", "password"]:
                    my_host.set_variable(key, value)

            # add to group
            my_group.add_host(my_host)
        self.inventory.add_group(my_group)

    def dynamic_inventory(self):
        """
        add hosts to inventory.
        :return:
        """
        if isinstance(self.resource, list):
            self.add_dynamic_group(self.resource, 'default_group')
        elif isinstance(self.resource, dict):
            for groupname, host_and_vars in self.resource.iteritems():
                self.add_dynamic_group(host_and_vars.get("hosts"), groupname, host_and_vars.get("vars"))


class ModelResultsCollector(CallbackBase):
    """
    ModelResultsCollector
    """
    def __init__(self, *args, **kwargs):
        """
        ModelResultsCollector
        :param args:
        :param kwargs:
        """
        super(ModelResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        """
        v2_runner_on_unreachable
        :param result:
        :return:
        """
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        """
        v2_runner_on_ok
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        """
        v2_runner_on_failed
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        self.host_failed[result._host.get_name()] = result


class ModelResultsCollectorToSave(CallbackBase):
    """
    ModelResultsCollectorToSave
    """
    def __init__(self, redisKey, logId, *args, **kwargs):
        """
        ModelResultsCollectorToSave
        :param redisKey:
        :param logId:
        :param args:
        :param kwargs:
        """
        super(ModelResultsCollectorToSave, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.redisKey = redisKey
        self.logId = logId

    def v2_runner_on_unreachable(self, result):
        """
        v2_runner_on_unreachable
        :param result:
        :return:
        """
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        data = "{host} | UNREACHABLE! => {stdout}".format(host=result._host.get_name, stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)
        if self.logId:
            AnsibleSaveResult.Model.insert(self.logId, data)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        """
        v2_runner_on_ok
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        if result._result.has_key('rc') and result._result.has_key('stdout'):
            data = "{host} | SUCCESS | rc={rc} >> \n{stdout}".format(host=result._host.get_name(), rc=result._result.get('rc'), stdout=result._result.get('stdout'))
        else:
            data = "{host} | SUCCESS >> {stdout}".format(host=result._host.get_name(), stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)

    def v2_runner_on_failed(self, result, *args, **kwargs):
        """
        v2_runner_on_failed
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        if result._result.has_key('rc') and result._result.has_key('stdout'):
            data = "{host} | FAILED | rc={rc} >> \n{stdout}".format(host=result._host.get_name(), rc=result._result.get('rc'), stdout=result._result.get('stdout'))
        else:
            data = "{host} | FAILED! => {stdout}".format(host=result._host.get_name(), stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)
        if self.logId:
            AnsibleSaveResult.Model.insert(self.logId, data)


class PlayBookResultsCollectorToSave(CallbackBase):
    """
    PlayBookResultsCollectorToSave
    """
    CALLBACK_VERSION = 2.0

    def __init__(self, redisKey, logId, *args, **kwargs):
        """
        PlayBookResultsCollectorToSave
        :param redisKey:
        :param logId:
        :param args:
        :param kwargs:
        """
        super(PlayBookResultsCollectorToSave, self).__init__(*args, **kwargs)
        self.task_ok = {}
        self.task_skipped = {}
        self.task_failed = {}
        self.task_status = {}
        self.task_unreachable = {}
        self.task_changed = {}
        self.redisKey = redisKey
        self.logId = logId

    def v2_runner_on_unreachable(self, result):
        """
        v2_runner_on_unreachable
        :param result:
        :return:
        """
        self.task_unreachable[result._host.get_name] = result._result
        msg = "fatal: [{host}]: UNREACHABLE! => {msg}\n".format(host=result._host.get_name(), msg=json.dumps(result._result))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_changed(self, result):
        """
        v2_runner_on_changed
        :param result:
        :return:
        """
        self.task_changed[result._host.get_name()] = result._result
        msg = "changed: [{host}]\n".format(host=result._host.get_name())
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_skipped(self, result):
        """
        v2_runner_on_skipped
        :param result:
        :return:
        """
        self.task_ok[result._host.get_name()] = result._result
        msg = "skipped: [{host}]\n".format(host=result._host.get_name())
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_play_start(self, play):
        """
        v2_runner_on_play_start
        :param play:
        :return:
        """
        name = play.get_name().strip()
        if not name:
            msg = u"PLAY"
        else:
            msg = u"PLAY [%s] " % name
        if len(msg) < 80:
            msg = msg + '*'*(79-len(msg))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def _print_task_banner(self, task):
        """
        _print_task_banner
        :param task:
        :return:
        """
        msg = "\nTASK [%s] " % (task.get_name().strip())
        if len(msg) < 80:
            msg = msg + '*'*(80-len(msg))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.redisKey, msg)

    def v2_playbook_on_task_start(self, task, is_conditional):
        """
        v2_playbook_on_task_start
        :param task:
        :param is_conditional:
        :return:
        """
        self._print_task_banner(task)

    def v2_playbook_on_cleanup_task_start(self, task):
        """
        v2_playbook_on_cleanup_task_start
        :param task:
        :return:
        """
        msg = "CLEANUP TASK [%s]" % task.get_name().strip()
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_playbook_on_handler_task_start(self, task):
        """
        v2_playbook_on_handler_task_start
        :param task:
        :return:
        """
        msg = "RUNNING HANDLER [%s]" % task.get_name().strip()
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_playbook_on_stats(self, stats):
        """
        v2_playbook_on_stats
        :param stats:
        :return:
        """
        msg = "\nPLAY RECAP *******************************************************************"
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)
            self.task_status[h] = {
                "ok": t['ok'],
                "changed": t['changed'],
                "unreachable": t['unreachable'],
                "skipped": t['skipped'],
                "failed": t['failures']
            }
            msg = "{host}\t\t: ok={ok}\tchanged={changed}\tunreachable={unreachable}\tskipped={skipped}\tfailed={failed}".format(
                host=h,
                ok=t['ok'], changed=t['changed'],
                unreachable=t['unreachable'],
                skipped=t['skipped'], failed=t['failures']
            )
            DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
            if self.logId:
                AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_ok(self, result):
        """
        v2_runner_item_on_ok
        :param result:
        :return:
        """
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if result._task.action in ('include', 'include_role'):
            return
        elif result._result.get('changed', False):
            msg = 'changed'
        else:
            msg = 'ok'
        if delegated_vars:
            msg += ": [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
        else:
            msg += ": [%s]" % result._host.get_name()
        msg += " => (item=%s)" % (json.dumps(self._get_item(result._result)))
        if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not  '_ansible_verbose_override' in result._result:
            msg += " => %s" % json.dumps(result._result)
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_failed(self, result):
        """
        v2_runner_item_on_failed
        :param result:
        :return:
        """
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        msg = "failed:"
        if delegated_vars:
            msg += " [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
        else:
            msg += " [%s] => (item=%s) => %s" % (result._host.get_name(), result._result['item'], self._dump_results(result._result))
        print msg
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_skipped(self, result):
        """
        v2_runner_item_on_skipped
        :param result:
        :return:
        """
        msg = "skipping: [%s] => (item=%s)" % (result._host.get_name(), self._get_item(result._result))
        if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += " => %s" % json.dumps(result._result)
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_retry(self, result):
        """
        v2_runner_retry
        :param result:
        :return:
        """
        task_name = result.task_name or result._task
        msg = "FAILED - RETRYING: %s (%d retries left)." % (task_name, result._result['retries'] - result._result['attempts'])
        if (self._display.verbosity > 2 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += " Result was: %s" % json.dumps(result._result, indent=4)
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:
            AnsibleSaveResult.PlayBook.insert(self.logId, msg)


class PlayBookResultsCollector(CallbackBase):
    """
    PlayBookResultsCollector
    """
    CALLBACK_VERSION = 2.0

    def __init__(self, *args, **kwargs):
        """
        PlayBookResultsCollector
        :param args:
        :param kwargs:
        """
        super(PlayBookResultsCollector, self).__init__(*args, **kwargs)
        self.task_ok = {}
        self.task_skipped = {}
        self.task_failed = {}
        self.task_status = {}
        self.task_unreachable = {}
        self.task_changed = {}

    def v2_runner_on_ok(self, result, *args, **kwargs):
        """
        v2_runner_on_ok
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        self.task_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        """
        v2_runner_on_failed
        :param result:
        :param args:
        :param kwargs:
        :return:
        """
        self.task_failed[result._host.get_name()] = result

    def v2_runner_on_unreachable(self, result):
        """
        v2_runner_on_unreachable
        :param result:
        :return:
        """
        self.task_unreachable[result._host.get_name()] = result

    def v2_runner_on_skipped(self, result):
        """
        v2_runner_on_skipped
        :param result:
        :return:
        """
        self.task_ok[result._host.get_name()] = result

    def v2_runner_on_changed(self, result):
        """
        v2_runner_on_changed
        :param result:
        :return:
        """
        self.task_changed[result._host.get_name()] = result

    def v2_playbook_on_stats(self, stats):
        """
        v2_playbook_on_stats
        :param stats:
        :return:
        """
        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)
            self.task_status[h] = {
                "ok": t['ok'],
                "changed": t['changed'],
                "unreachable": t['unreachable'],
                "skipped": t['skipped'],
                "failed": t['failures']
            }


class ANSRunner(object):
    """
    This is a General object for parallel execute modules.
    """
    def __init__(self, resource, redisKey=None, logId=None, **kwargs):
        """
        ANSRunner
        :param resource:
        :param redisKey:
        :param logId:
        :param args:
        :param kwargs:
        """
        self.resource = resource
        self.inventory = None
        self.variable_manager = None
        self.loader = None
        self.options = None
        self.passwords = None
        self.callback = None
        self.__initializeData(kwargs)
        self.results_raw = {}
        self.redisKey = redisKey
        self.logId = logId

    def __initializeData(self, kwargs):
        """
        初始化 ansible
        :param kwargs:
        :return:
        """
        Options = namedtuple(
            'Options',
            ['connection', 'module_path', 'forks', 'timeout', 'remote_user',
             'ask_pass', 'private_key_file', 'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args',
             'scp_extra_args', 'become', 'become_method', 'become_user', 'ask_value_pass',
             'verbosity', 'check', 'listhosts', 'listtasks', 'listtags', 'syntax']
        )
        self.variable_manager = VariableManager()
        self.loader = DataLoader()
        self.options = Options(
            connection='smart',
            module_path=None,
            forks=100,
            timeout=10,
            remote_user=kwargs.get('remote_user', 'root'),
            ask_pass=False,
            private_key_file=None,
            ssh_common_args=None,
            ssh_extra_args=None,
            sftp_extra_args=None,
            scp_extra_args=None,
            become=True,
            become_method=kwargs.get('become_method', 'sudo'),
            become_user=kwargs.get('become_user', 'root'),
            verbosity=kwargs.get('verbosity', None),
            check=False,
            listhosts=False,
            listtasks=False,
            listtags=False,
            syntax=False,
            ask_value_pass=False,
        )
        self.passwords = dict(sshpass=None, becomepass=None)
        self.inventory = MyInventory(self.resource, self.loader, self.variable_manager).inventory
        self.variable_manager.set_inventory(self.inventory)

    def run_model(self, host_list, module_name, module_args):
        """
        run module from ansible ad-hoc.
        :param host_list:
        :param module_name: ansible module name
        :param module_args: ansible module args
        :return:
        """
        play_source = dict(
            name="Ansible Play",
            hosts=host_list,
            gather_facts='no',
            tasks=[dict(action=dict(module=module_name, args=module_args))]
        )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
        tqm = None
        if self.redisKey or self.logId:
            self.callback = ModelResultsCollectorToSave(self.redisKey, self.logId)
        else:
            self.callback = ModelResultsCollector()
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
            )
            tqm._stdout_callback = self.callback
            constants.HOST_KEY_CHECKING = False
            tqm.run(play)
        except Exception as err:
            if self.redisKey:
                DsRedis.OpsAnsibleModel.lpush(self.redisKey, data=err)
            if self.logId:
                AnsibleSaveResult.Model.insert(self.logId, err)
        finally:
            if tqm is not None:
                tqm.cleanup()

    def run_playbook(self, host_list, playbook_path, extra_vars=dict()):
        """
        run ansible playbook
        :param host_list:
        :param playbook_path:
        :param extra_vars:
        :return:
        """
        try:
            if self.redisKey or self.logId:
                self.callback = PlayBookResultsCollectorToSave(self.redisKey, self.logId)
            else:
                self.callback = PlayBookResultsCollector()
            extra_vars['host'] = ','.join(host_list)
            self.variable_manager.extra_vars = extra_vars
            executor = PlaybookExecutor(
                playbooks=[playbook_path],
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                options=self.options,
                passwords=self.passwords,
            )
            executor._tqm._stdout_callback = self.callback
            constants.HOST_KEY_CHECKING = False
            constants.DEPRECATION_WARNINGS = False
            executor.run()
        except Exception as err:
            print err
            if self.redisKey:
                DsRedis.OpsAnsibleModel.lpush(self.redisKey, data=err)
            if self.logId:
                AnsibleSaveResult.Model.insert(self.logId, err)
            return False

    def get_model_result(self):
        """
        get_model_result
        :return: json results_raw
        """
        self.results_raw = {'success': {}, 'failed': {}, 'unreachable': {}}
        for host, result in self.callback.host_ok.items():
            self.results_raw['success'][host] = result._result
        for host, result in self.callback.host_failed.items():
            self.results_raw['failed'][host] = result._result
        for host, result in self.callback.host_unreachable.items():
            self.results_raw['unreachable'][host] = result._result
        return json.dumps(self.results_raw)

    def get_playbook_result(self):
        """
        get_playbook_result
        :return: results_raw
        """
        self.results_raw = {'skipped': {}, 'failed': {}, 'ok': {}, "status": {}, 'unreachable': {}, "changed": {}}
        for host, result in self.callback.task_ok.items():
            self.results_raw['ok'][host] = result
        for host, result in self.callback.task_failed.items():
            self.results_raw['failed'][host] = result
        for host, result in self.callback.task_status.items():
            self.results_raw['status'][host] = result
        for host, result in self.callback.task_changed.items():
            self.results_raw['changed'][host] = result
        for host, result in self.callback.task_skipped.items():
            self.results_raw['skipped'][host] = result
        for host, result in self.callback.task_unreachable.items():
            self.results_raw['unreachable'][host] = result
        return self.results_raw

    def handle_cmdb_data(self, data):
        """
        处理 setup 返回结果方法
        :param data:
        :return:
        """
        data_list = []
        for k, v in json.loads(data).items():
            if k == "success":
                for x, y in v.items():
                    cmdb_data = {}
                    data = y.get('ansible_facts')
                    disk_size = 0
                    cpu = data['ansible_processor'][-1]
                    for k, v in data['ansible_devices'].items():
                        if k[0:2] in ['sd', 'hd', 'ss', 'vd']:
                            disk = int((int(v.get('sectors')) * int(v.get('sectorsize')))/1024/1024)
                            disk_size = disk_size + disk
                    cmdb_data['serial'] = data['ansible_product_serial'].split()[0]
                    cmdb_data['ip'] = x
                    cmdb_data['cpu'] = cpu.replace('@', '')
                    cmdb_data['ram_total'] = int(data['ansible_memtotal_mb'])
                    cmdb_data['disk_total'] = int(disk_size)
                    cmdb_data['system'] = data['ansible_distribution'] + ' ' + data['ansible_distribution_version'] + ' ' + data['ansible_userspace_bits']
                    cmdb_data['model'] = data['ansible_product_name'].split(':')[0]
                    cmdb_data['cpu_number'] = data['ansible_processor_count']
                    cmdb_data['vcpu_number'] = data['ansible_processor_vcpus']
                    cmdb_data['cpu_core'] = data['ansible_processor_cores']
                    cmdb_data['hostname'] = data['ansible_hostname']
                    cmdb_data['kernel'] = str(data['ansible_kernel'])
                    cmdb_data['manufacturer'] = data['ansible_system_vendor']
                    if data['ansible_selinux']:
                        cmdb_data['selinux'] = data['ansible_selinux'].get('status')
                    else:
                        cmdb_data['selinux'] = 'disabled'
                    cmdb_data['swap'] = int(data['ansible_swaptotal_mb'])
                    # 获取网卡资源
                    nks = []
                    for nk in data.keys():
                        if re.match(r"^ansible_(eth|bind|eno|ens|em)\d+?", nk):
                            device = data.get(nk).get('device')
                            try:
                                address = data.get(nk).get('ipv4').get('address')
                            except:
                                address = 'unkown'
                            macaddress = data.get(nk).get('macaddress')
                            module = data.get(nk).get('module')
                            mtu = data.get(nk).get('mtu')
                            if data.get(nk).get('active'):
                                active = 1
                            else:
                                active = 0
                            nks.append(
                                {
                                    "device": device,
                                    "address": address,
                                    "macaddress": macaddress,
                                    "module": module,
                                    "mtu": mtu,
                                    "active": active
                                }
                            )
                    cmdb_data['status'] = 0
                    cmdb_data['nks'] = nks
                    data_list.append(cmdb_data)
            elif k == "unreachable":
                for x, y in v.items():
                    cmdb_data = {}
                    cmdb_data['status'] = 1
                    cmdb_data['ip'] = x
                    data_list.append(cmdb_data)
        if data_list:
            return data_list
        else:
            return False

    def handle_cmdb_crawHw_data(self, data):
        """
        handle_cmdb_crawHw_data
        :param data:
        :return:
        """
        data_list = []
        for k, v in json.loads(data).items():
            if k == "success":
                for x, y in v.items():
                    cmdb_data = {}
                    cmdb_data['ip'] = x
                    data = y.get('ansible_facts')
                    cmdb_data['mem_info'] = data.get('ansible_mem_detailed_info')
                    cmdb_data['disk_info'] = data.get('ansible_disk_detailed_info')
                    data_list.append(cmdb_data)
        if data_list:
            return data_list
        else:
            return False

    def handle_model_data(self, data, module_name, module_args=None):
        """
        处理 ansible 模块输出内容
        :param data:
        :param module_name:
        :param module_args:
        :return:
        """
        module_data = json.loads(data)
        failed = module_data.get('failed')
        success = module_data.get('success')
        unreachable = module_data.get('unreachable')
        data_list = []
        if module_name == "raw":
            if failed:
                for x, y in failed.items():
                    data = {}
                    data['ip'] = x
                    try:
                        data['msg'] = y.get('stdout').replace('\t\t', '<br>').replace('\r\n', '<br>').replace('\t', '<br>')
                    except:
                        data['msg'] = None
                    if y.get('rc') == 0:
                        data['status'] = 'succeed'
                    else:
                        data['status'] = 'failed'
                    data_list.append(data)
            elif success:
                for x, y in success.items():
                    data = {}
                    data['ip'] = x
                    try:
                        data['msg'] = y.get('stdout').replace('\t\t', '<br>').replace('\r\n', '<br>').replace('\t', '<br>')
                    except:
                        data['msg'] = None
                    if y.get('rc') == 0:
                        data['status'] = 'succeed'
                    else:
                        data['status'] = 'failed'
                    data_list.append(data)
        elif module_name == "ping":
            if success:
                for x, y in success.items():
                    data = {}
                    data['ip'] = x
                    if y.get('ping'):
                        data['msg'] = y.get('ping')
                        data['status'] = 'succeed'
                    data_list.append(data)
        else:
            if success:
                for x, y in success.items():
                    data = {}
                    data['ip'] = x
                    if y.get('invocation'):
                        data['msg'] = "Ansible %s with %s execute success." % (module_name, module_args)
                        data['status'] = 'succeed'
                    data_list.append(data)

            elif failed:
                for x, y in failed.items():
                    data = {}
                    data['ip'] = x
                    data['msg'] = y.get('msg')
                    data['status'] = 'failed'
                    data_list.append(data)
        if unreachable:
            for x, y in unreachable.items():
                data = {}
                data['ip'] = x
                data['msg'] = y.get('msg')
                data['status'] = 'failed'
                data_list.append(data)
        if data_list:
            return data_list
        else:
            return False


if __name__ == '__main__':
    resource = [
        {"hostname": "192.168.1.235"},
        {"hostname": "192.168.1.234"},
        {"hostname": "192.168.1.233"},
    ]

    rbt = ANSRunner(resource, redisKey='1')
    rbt.run_model(
        host_list=["192.168.1.235", "192.168.1.234", "192.168.1.233"],
        module_name='yum',
        module_args="name=htop state=present"
    )
