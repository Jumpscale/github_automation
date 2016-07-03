#!/usr/local/bin/jspython
from JumpScale import j
import argparse

def get_args():

    parser = argparse.ArgumentParser(
        description='installs cockpit with github ays templates on a docker')
    parser.add_argument(
        '--ip', type=str, help='IP address', required=True)
    parser.add_argument(
       '--repo', type=str, help='github repo for github ays templates', required=True)
    args = parser.parse_args()
    ip = args.ip
    repo = args.repo
    return ip, repo


def main():
    ip, repo_url = get_args()
    executor = j.tools.executor.getSSHBased(ip)
    c = executor.cuisine
    c.docker.install()
    executor.execute("docker run -d -p 222:22 jumpscale/g8cockpit  /sbin/my_init")
    docker_exec = j.tools.executor.getSSHBased(ip, 222, passwd="gig1234")
    docker_cuisine = docker_exec.cuisine
    docker_cuisine.core.file_append("/optvar/hrd/system/atyourservice.hrd", """
    metadata.github =
        url:'https://github.com/jumpscale/ays_gig_github_dev_process',
        branch:'master',
    """)
    docker_cuisine.git.pullRepo(repo_url)

if __name__ == '__main__':
    main()

