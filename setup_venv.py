#!/usr/bin/python

import subprocess

# path to app engine in the gcloud tools
GCLOUD_APP_ENGINE_PATH = '/platform/google_appengine'
GCLOUD_BIN_SUFFIX = '/bin/gcloud'

def main():
    # find the gcloud command and app engine paths
    gcloud_command = subprocess.check_output(('which', 'gcloud')).strip()

    if not gcloud_command.endswith(GCLOUD_BIN_SUFFIX):
        raise ValueError("expected gcloud path to end in %s (found %s)" % (
            GCLOUD_BIN_SUFFIX, gcloud_command))
    gcloud_dir = gcloud_command[:-len(GCLOUD_BIN_SUFFIX)]
    print 'Using Google Cloud tools in', gcloud_dir

    # setup the virtualenv
    subprocess.check_call(('virtualenv', 'venv'))
    subprocess.check_call(('venv/bin/pip', 'install', '-r', 'requirements.txt'))

    # update the virtualenv path to find app engine libraries
    f = open('venv/lib/python2.7/site-packages/app_engine.pth', 'w')
    f.write(gcloud_dir + GCLOUD_APP_ENGINE_PATH + '\n')
    f.write('import dev_appserver; dev_appserver.fix_sys_path()\n')
    f.close()


if __name__ == '__main__':
    main()
