#!/usr/bin/env python
# -*- coding=utf-8 -*-
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth.decorators import permission_required


@login_required()
@permission_required('omba.can_add_ansible_playbook', login_url='/noperm/')
def finder(request):
    return render(
        request,
        'elfinder/finder.html',
        {
            "user": request.user
        }
    )
