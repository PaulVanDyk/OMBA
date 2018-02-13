#!/usr/bin/env python
# -*- coding=utf-8 -*-

import os, json, re
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
        super(ModelResultsCollector, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.host_failed[result._host.get_name()] = result

class ModelResultsCollectorToSave(CallbackBase):
    """
    ModelResultsCollectorToSave
    """
    def __init__(self, redisKey, logId, *args, **kwargs):
        super(ModelResultsCollectorToSave, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.redisKey = redisKey
        self.logId = logId

    def v2_runner_on_unreachable(self, result):
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        data = "{host} | UNREACHABLE! => {stdout}".format(host=result._host.get_name, stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)
        if self.logId:AnsibleSaveResult.Model.insert(self.logId, data)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        if result._result.has_key('rc') and result._result.has_key('stdout'):
            data = "{host} | SUCCESS | rc={rc} >> \n{stdout}".format(host=result._host.get_name(), rc=result._result.get('rc'), stdout=result._result.get('stdout'))
        else:
            data = "{host} | SUCCESS >> {stdout}".format(host=result._host.get_name(), stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)

    def v2_runner_on_failed(self, result, *args, **kwargs):
        for remove_key in ('changed', 'invocation'):
            if remove_key in result._result:
                del result._result[remove_key]
        if result._result.has_key('rc') and result._result.has_key('stdout'):
            data = "{host} | FAILED | rc={rc} >> \n{stdout}".format(host=result._host.get_name(), rc=result._result.get('rc'), stdout=result._result.get('stdout'))
        else:
            data = "{host} | FAILED! => {stdout}".format(host=result._host.get_name(), stdout=json.dumps(result._result, indent=4))
        DsRedis.OpsAnsibleModel.lpush(self.redisKey, data)
        if self.logId:AnsibleSaveResult.Model.insert(self.logId, data)

class PlayBookResultsCollectorToSave(CallbackBase):
    """
    PlayBookResultsCollectorToSave
    """
    CALLBACK_VERSION = 2.0
    def __init__(self, redisKey, logId, *args, **kwargs):
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
        self.task_unreachable[result._host.get_name] = result._result
        msg = "fatal: [{host}]: UNREACHABLE! => {msg}\n".format(host=result._host.get_name(), msg=json.dumps(result._result))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_changed(self, result):
        self.task_changed[result._host.get_name()] = result._result
        msg = "changed: [{host}]\n".format(host=result._host.get_name())
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_skipped(self, result):
        self.task_ok[result._host.get_name()] = result._result
        msg = "skipped: [{host}]\n".format(host=result._host.get_name())
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_on_play_start(self, play):
        name = play.get_name().strip()
        if not name:
            msg = u"PLAY"
        else:
            msg = u"PLAY [%s] " % name
        if len(msg) < 80:msg = msg + '*'*(79-len(msg))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def _print_task_banner(self, task):
        msg = "\nTASK [%s] " % (task.get_name().strip())
        if len(msg) < 80:msg = msg + '*'*(80-len(msg))
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.redisKey, msg)

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._print_task_banner(task)

    def v2_playbook_on_cleanup_task_start(self, task):
        msg = "CLEANUP TASK [%s]" % task.get_name().strip()
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_playbook_on_handler_task_start(self, task):
        msg = "RUNNING HANDLER [%s]" % task.get_name().strip()
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_playbook_on_stats(self, stats):
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
            if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_ok(self, result):
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
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_failed(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        msg = "failed:"
        if delegated_vars:
            msg += " [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
        else:
            msg += " [%s] => (item=%s) => %s" % (result._host.get_name(), result._result['item'], self._dump_results(result._result))
        print msg
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_item_on_skipped(self, result):
        msg = "skipping: [%s] => (item=%s)" % (result._host.get_name(), self._get_item(result._result))
        if (self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += " => %s" % json.dumps(result._result)
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId:AnsibleSaveResult.PlayBook.insert(self.logId, msg)

    def v2_runner_retry(self, result):
        task_name = result.task_name or result._task
        msg = "FAILED - RETRYING: %s (%d retries left)." % (task_name, result._result['retries'] - result._result['attempts'])
        if (self._display.verbosity > 2 or '_ansible_verbose_always' in result._result) and not '_ansible_verbose_override' in result._result:
            msg += " Result was: %s" % json.dumps(result._result, indent=4)
        DsRedis.OpsAnsiblePlayBook.lpush(self.redisKey, msg)
        if self.logId: AnsibleSaveResult.PlayBook.insert(self.logId, msg)

class PlayBookResultsCollector(CallbackBase):
    """
    PlayBookResultsCollector
    """
    CALLBACK_VERSION = 2.0
    def __init__(self, *args, **kwargs):
        """

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
        self.task_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.task_failed[result._host.get_name()] = result

    def v2_runner_on_unreachable(self, result):
        self.task_unreachable[result._host.get_name()] = result

    def v2_runner_on_skipped(self, result):
        self.task_ok[result._host.get_name()] = result

    def v2_runner_on_changed(self, result):
        self.task_changed[result._host.get_name()] = result

    def v2_playbook_on_stats(self, stats):
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
    def __init__(self, resource, redisKey=None, logId=None, *args, **kwargs):
        """

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
            remote_user=kwargs.get('remote_user','root'),
            ask_pass=False,
            private_key_file=None,
            ssh_common_args=None,
            ssh_extra_args=None,
            sftp_extra_args=None,
            scp_extra_args=None,
            become=True,
            become_method=kwargs.get('become_method','sudo'),
            become_user=kwargs.get('become_user','root'),
            verbosity=kwargs.get('verbosity',None),
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
        if self.redisKey or self.logId:self.callback = ModelResultsCollectorToSave(self.redisKey, self.logId)
        else:self.callback = ModelResultsCollector()
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
            if self.redisKey:DsRedis.OpsAnsibleModel.lpush(self.redisKey, data=err)
            if self.logId:AnsibleSaveResult.Model.insert(self.logId, err)
        finally:
            if tqm is not None:
                tqm.cleanup()