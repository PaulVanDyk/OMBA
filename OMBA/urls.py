"""OMBA URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from OMBA.views import (
    ansible
)
from OMBA.restfull import (
    ansible_api
)

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^apps/$', ansible.apps_list),
    url(r'^apps/model/$', ansible.apps_model),
    url(r'^apps/script/online/$', ansible.apps_script_online),
    url(r'^apps/script/list/$', ansible.apps_script_list),
    url(r'^apps/script/file/(?P<pid>[0-9]+)/$', ansible.apps_script_file),
    url(r'^apps/script/run/(?P<pid>[0-9]+)/$', ansible.apps_script_online_run),
    url(r'^apps/run/$', ansible.ansible_run),
    url(r'^apps/log/$', ansible.ansible_log),
    url(r'^apps/log/(?P<model>[a-z]+)/(?P<pid>[0-9]+)/$', ansible.ansible_log_view),
    url(r'^apps/playbook/upload/$', ansible.apps_upload),
    url(r'^apps/playbook/online/$', ansible.apps_online),
    url(r'^apps/playbook/file/(?P<pid>[0-9]+)/$', ansible.apps_playbook_file),
    url(r'^apps/playbook/run/(?P<pid>[0-9]+)/$', ansible.apps_playbook_run),
    url(r'^apps/playbook/modf/(?P<pid>[0-9]+)/$', ansible.apps_playbook_modf),
    url(r'^apps/playbook/online/modf/(?P<pid>[0-9]+)/$', ansible.apps_playbook_online_modf),
    url(r'^api/playbook/$', ansible_api.playbook_list),
    url(r'^api/playbook/(?P<id>[0-9]+)/$', ansible_api.playbook_detail),
    url(r'^api/logs/ansible/model/(?P<id>[0-9]+)/$', ansible_api.modelLogsdetail),
    url(r'^api/logs/ansible/playbook/(?P<id>[0-9]+)/$', ansible_api.playbookLogsdetail),
]
