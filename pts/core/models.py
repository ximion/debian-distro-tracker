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
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from pts.core.utils import get_or_none


@python_2_unicode_compatible
class Keyword(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class EmailUserManager(models.Manager):
    """
    A custom Manager for the ``EmailUser`` model.
    """
    def is_user_subscribed_to(self, user_email, package_name):
        """
        Checks if the given user is subscribed to the given package.
        """
        user = get_or_none(EmailUser, email=user_email)
        if not user:
            return False
        else:
            return user.is_subscribed_to(package_name)


@python_2_unicode_compatible
class EmailUser(models.Model):
    email = models.EmailField(max_length=254, unique=True)
    default_keywords = models.ManyToManyField(Keyword)

    objects = EmailUserManager()

    def __str__(self):
        return self.email

    def is_subscribed_to(self, package):
        """
        Checks if the user is subscribed to the given package.
        ``package`` can be either a str representing the name of the package
        or a ``Package`` instance.
        """
        if not isinstance(package, Package):
            package = get_or_none(Package, name=package)
            if not package:
                return False

        return package in (
            subscription.package
            for subscription in self.subscription_set.all_active()
        )


class PackageManager(models.Manager):
    """
    A custom Manager for the ``Package`` model.
    """
    def exists_with_name(self, package_name):
        """
        Returns True if a package with the given name exists.
        """
        return self.filter(name=package_name).exists()


@python_2_unicode_compatible
class Package(models.Model):
    name = models.CharField(max_length=100, unique=True)
    subscriptions = models.ManyToManyField(EmailUser, through='Subscription')

    objects = PackageManager()

    def __str__(self):
        return self.name


class SubscriptionManager(models.Manager):
    def create_for(self, package_name, email, active=True):
        package = get_or_none(Package, name=package_name)
        if not package:
            return None
        email_user, created = EmailUser.objects.get_or_create(
            email=email)

        subscription, _ = self.get_or_create(email_user=email_user,
                                             package=package)
        subscription.active = active
        subscription.save()

        return subscription

    def unsubscribe(self, package_name, email):
        package = get_or_none(Package, name=package_name)
        email_user = get_or_none(EmailUser, email=email)
        if not package or not email_user:
            return False
        subscription = get_or_none(
            Subscription, email_user=email_user, package=package)
        if subscription:
            subscription.delete()
        return True

    def get_for_email(self, email):
        email_user = get_or_none(EmailUser, email=email)
        if not email_user:
            return []
        return email_user.subscription_set.all_active()

    def all_active(self):
        """
        Returns all active subscriptions
        """
        return self.filter(active=True)


@python_2_unicode_compatible
class Subscription(models.Model):
    email_user = models.ForeignKey(EmailUser)
    package = models.ForeignKey(Package)
    active = models.BooleanField(default=True)
    _keywords = models.ManyToManyField(Keyword)
    _use_user_default_keywords = models.BooleanField(default=True)

    objects = SubscriptionManager()

    class KeywordsAdapter(object):
        """
        An adapter for accessing a Subscription's keywords.

        When a Subscription is initially created, it uses the default keywords
        of the user. Only after modifying the subscription-specific keywords,
        should it use a different set of keywords.

        This class allows the clients of the ``Subscription`` class to access
        the keywords field without having to think about whether the
        subscription is using the user's keywords or not, rather the whole
        process is handled automatically and seamlessly.
        """
        def __init__(self, subscription):
            #: Keep a reference to the original subscription object
            self._subscription = subscription

        def __getattr__(self, name):
            # Methods which modify the set should cause it to become unlinked
            # from the user.
            if name in ('add', 'remove', 'create', 'clear', 'bulk_create'):
                self._unlink_from_user()
            return getattr(self._get_manager(), name)

        def _get_manager(self):
            """
            Helper method which returns the appropriate manager depending on
            whether the subscription is still using the user's keywords or not.
            """
            if self._subscription._use_user_default_keywords:
                manager = self._subscription.email_user.default_keywords
            else:
                manager = self._subscription._keywords
            return manager

        def _unlink_from_user(self):
            """
            Helper method which unlinks the subscription from the user's
            default keywords.
            """
            if self._subscription._use_user_default_keywords:
                # Do not use the user's keywords anymore
                self._subscription._use_user_default_keywords = False
                # Copy the user's keywords
                user = self._subscription.email_user
                for keyword in user.default_keywords.all():
                    self._subscription._keywords.add(keyword)
                self._subscription.save()

    def __init__(self, *args, **kwargs):
        models.Model.__init__(self, *args, **kwargs)
        self.keywords = Subscription.KeywordsAdapter(self)

    def __str__(self):
        return str(self.email_user) + ' ' + str(self.package)


class BinaryPackageManager(models.Manager):
    """
    A custom Manager for the ``BinaryPackage`` model.
    """
    def exists_with_name(self, package_name):
        """
        Returns True if a package with the given name exists.
        """
        return self.filter(name=package_name).exists()

    def get_by_name(self, package_name):
        """
        Returns a ``BinaryPackage`` object for the given package name.
        """
        return self.get(name=package_name)


@python_2_unicode_compatible
class BinaryPackage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    source_package = models.ForeignKey(Package)

    objects = BinaryPackageManager()

    def __str__(self):
        return self.name
