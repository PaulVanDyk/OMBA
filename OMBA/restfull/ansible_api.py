#!/usr/bin/env python
# -*- coding=utf-8 -*-
from OMBA.serializers import *
from OMBA.models import *
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth.decorators import permission_required


@api_view(['GET', 'POST'])
@permission_required('OMBA.can_read_ansible_playbook', raise_exception=True)
def playbook_list(request, format=None):
    """
    List all order, or create a server assets order.
    :param request: 
    :param format: 
    :return: 
    """
    if request.method == 'GET':
        snippets = Ansible_Playbook.objects.all()
        serializer = AnsiblePlaybookSerializer(snippets, many=True)
        return Response(serializer.data)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_required('OMBA.can_delete_ansible_playbook', raise_exception=True)
def playbook_detail(request, id, format=None):
    """
    Retrieve, update or delete a server instance.
    :param request:
    :param id:
    :param format:
    :return:
    """
    try:
        snippet = Ansible_Playbook.objects.get(id=id)
    except Ansible_Playbook.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = AnsiblePlaybookSerializer(snippet)
        return Response(serializer.data)
    elif request.method == 'DELETE':
        if not request.user.has_perm('OMBA.can_delete_playbook'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        snippet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_required('OMBA.can_delete_log_ansible_model', raise_exception=True)
def modelLogsdetail(request, id, format=None):
    """
    Retrieve, update or delete a server assets instance.
    :param request: 
    :param id: 
    :param format: 
    :return: 
    """
    try:
        snippet = Log_Ansible_Model.objects.get(id=id)
    except Log_Ansible_Model.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = AnsibleModelLogsSerializer(snippet)
        return Response(serializer.data)
    elif request.method == 'DELETE':
        if not request.user.has_perm('OMBA.can_delete_log_ansible_model'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        snippet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_required('OMBA.can_delete_log_ansible_playbook', raise_exception=True)
def playbookLogsdetail(request, id, format=None):
    """
    Retrieve, update or delete a server assets instance.
    :param request: 
    :param id: 
    :param format: 
    :return: 
    """
    try:
        snippet = Log_Ansible_Playbook.objects.get(id=id)
    except Log_Ansible_Playbook.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        serializer = AnsiblePlaybookLogsSerializer(snippet)
        return Response(serializer.data)
    elif request.method == 'DELETE':
        if not request.user.has_perm('OMBA.can_delete_log_ansible_playbook'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        snippet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
