# -*- coding: utf-8 -*-

# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.

from __future__ import unicode_literals
from django.utils.safestring import mark_safe
from django.utils.http import urlencode
from pts.core.utils import get_or_none
from pts.core.models import Repository
from pts.core.panels import BasePanel
from pts.core.panels import LinksPanel
from pts.core.panels import TemplatePanelItem
from pts.vendor.debian.models import LintianStats
from pts.vendor.debian.models import PackageExcuses


class LintianLink(LinksPanel.ItemProvider):
    """
    If there are any known lintian issues for the package, provides a link to
    the lintian page.
    """
    def get_panel_items(self):
        try:
            lintian_stats = self.package.lintian_stats
        except LintianStats.DoesNotExist:
            return []

        if sum(lintian_stats.stats.values()):
            warnings, errors = (
                lintian_stats.stats.get('warnings', 0),
                lintian_stats.stats.get('errors', 0))
            has_errors_or_warnings = warnings or errors
            # Get the full URL only if the package does not have any errors or
            # warnings
            url = lintian_stats.get_lintian_url(full=not has_errors_or_warnings)
            return [
                TemplatePanelItem('debian/lintian-link.html', {
                    'lintian_stats': lintian_stats.stats,
                    'lintian_url': url,
                })
            ]

        return []


class BuildLogCheckLinks(LinksPanel.ItemProvider):
    def get_panel_items(self):
        has_experimental = False
        experimental_repo = get_or_none(Repository, name='experimental')
        if experimental_repo:
            has_experimental = experimental_repo.has_source_package_name(
                self.package.name)

        query_string = urlencode({'p': self.package.name})
        try:
            self.package.build_logcheck_stats
            has_checks = True
        except:
            has_checks = False
        logcheck_url = "http://qa.debian.org/bls/packages/{hash}/{pkg}.html".format(
            hash=self.package.name[0], pkg=self.package.name)

        return [
            TemplatePanelItem('debian/logcheck-links.html', {
                'package_query_string': query_string,
                'has_checks': has_checks,
                'logcheck_url': logcheck_url,
                'has_experimental': has_experimental,
            })
        ]


class TransitionsPanel(BasePanel):
    template_name = 'debian/transitions-panel.html'
    panel_importance = 2
    position = 'center'
    title = 'testing migrations'

    @property
    def context(self):
        try:
            excuses = self.package.excuses.excuses
        except PackageExcuses.DoesNotExist:
            excuses = None
        if excuses:
            excuses = [mark_safe(excuse) for excuse in excuses]
        return {
            'transitions': self.package.package_transitions.all(),
            'excuses': excuses,
            'package_name': self.package.name,
        }
