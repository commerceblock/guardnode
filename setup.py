#!/usr/bin/env python3
from setuptools import setup, find_packages
import os

setup(name='guardnode',
      version='0.3',
      description='Guardnode Daemon',
      author='CommerceBlock',
      author_email='nikolaos@commerceblock.com',
      url='http://github.com/commerceblock/guardnode',
      packages=find_packages(),
      scripts=[],
      include_package_data=True,
      data_files=[],
)
