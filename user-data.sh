#!/bin/bash
set -euo pipefail
yum install -y nginx
systemctl enable nginx
systemctl start nginx
