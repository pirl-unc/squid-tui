# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import os
from ..app import run as app_run


from squidlib import __version__


def run():
    parser = argparse.ArgumentParser(
        prog="squid-tui",
        description="Squid-TUI: Slurm QUeue Interactive Dashboard",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show jobs for all users.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=os.environ.get("USER"),
        help="Show jobs for a specific user (default: $USER).",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=180,
        help="Auto-refresh interval in seconds (default: 180).",
    )
    args = parser.parse_args()

    user = None if args.all else args.user

    app_run(user=user, refresh_interval=args.refresh)
