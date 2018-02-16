#!/usr/bin/env python
# -*- coding=utf-8 -*-
import uuid
import os
import json
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
