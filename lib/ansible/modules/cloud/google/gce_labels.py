#!/usr/bin/python
# Copyright 2017 Google Inc.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: gce_labels
version_added: '2.4'
short_description: Create, Update or Destory GCE Labels.
description:
    - Create, Update or Destory GCE Labels on instances, disks, snapshots, etc.
      When specifying the GCE resource, users may specifiy the full URL for
      the resource (its 'self_link'), or the individual parameters of the
      resource (type, location, name). Examples for the two options can be
      seen in the documentaion.
      See U(https://cloud.google.com/compute/docs/label-or-tag-resources) for
      more information about GCE Labels. Labels are gradually being added to
      more GCE resources, so this module will need to be updated as new
      resources are added to the GCE (v1) API.
requirements:
  - 'python >= 2.6'
  - 'google-api-python-client >= 1.6.2'
  - 'google-auth >= 1.0.0'
  - 'google-auth-httplib2 >= 0.0.2'
notes:
  - Labels support resources such as  instances, disks, images, etc. See
    U(https://cloud.google.com/compute/docs/labeling-resources) for the list
    of resources available in the GCE v1 API (not alpha or beta).
author:
  - 'Eric Johnson (@erjohnso) <erjohnso@google.com>'
options:
  labels:
    description:
       - The list of labels (key/value pairs) to add to set on the resource.
    required: false
  resource_url:
    description:
       - The 'self_link' for the resource (instance, disk, snapshot, etc)
    required: false
  resource_type:
    description:
       - The type of resource (instances, disks, snapshots, images)
    required: false
  resource_location:
    description:
       - The location of resource (global, us-central1-f, etc.)
    required: false
  resource_name:
    description:
       - The name of resource.
    required: false
'''

EXAMPLES = '''
- name: Set GCE Labels on an existing instance (using resource_url)
  gce_labels:
    service_account_email: "{{ service_account_email }}"
    credentials_file: "{{ credentials_file }}"
    project_id: "{{ project_id }}"
    labels:
      webserver-frontend: homepage
      environment: test
      experiment-name: kennedy
    resource_url: https://www.googleapis.com/compute/beta/projects/myproject/zones/us-central1-f/instances/example-instance
    state: present
- name: Set GCE Labels on an image (using resource params)
  gce_labels:
    service_account_email: "{{ service_account_email }}"
    credentials_file: "{{ credentials_file }}"
    project_id: "{{ project_id }}"
    labels:
      webserver-frontend: homepage
      environment: test
      experiment-name: kennedy
    resource_type: images
    resource_location: global
    resource_name: my-custom-image
    state: present
- name: Clear all labels on an GCE image
  gce_labels:
    service_account_email: "{{ service_account_email }}"
    credentials_file: "{{ credentials_file }}"
    project_id: "{{ project_id }}"
    resource_type: images
    resource_location: global
    resource_name: my-custom-image
    state: absent
'''

RETURN = '''
labels:
    description: List of labels
    returned: Always.
    type: dict
    sample: [ { 'webserver-frontend': 'homepage', 'environment': 'test', 'environment-name': 'kennedy' } ]
resource_url:
    description: The 'self_link' of the GCE resource.
    returned: Always.
    type: str
    sample: 'https://www.googleapis.com/compute/beta/projects/myproject/zones/us-central1-f/instances/example-instance'
resource_type:
    description: The type of the GCE resource.
    returned: Always.
    type: str
    sample: instances
resource_location:
    description: The location of the GCE resource.
    returned: Always.
    type: str
    sample: us-central1-f
resource_name:
    description: The name of the GCE resource.
    returned: Always.
    type: str
    sample: my-happy-little-instance
state:
    description: state of the labels
    returned: Always.
    type: str
    sample: present
'''

try:
    from ast import literal_eval
    HAS_PYTHON26 = True
except ImportError:
    HAS_PYTHON26 = False

# import module snippets
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.gcp import check_params, get_google_api_client, GCPUtils

UA_PRODUCT = 'ansible-gce_labels'
UA_VERSION = '0.0.1'
GCE_API_VERSION = 'beta'  # change to 'v1' when Labels hits GA

# TODO(all): As Labels are added to more GCE resources, this list will need to
# be updated (along with some code changes below). The list can *only* include
# resources from the 'v1' GCE API and will *not* work with 'beta' or 'alpha'.
KNOWN_RESOURCES = ['instances', 'disks', 'snapshots', 'images']


def _fetch_resource(client, params):
    if params['resource_url']:
        if not params['resource_url'].startswith('https://www.googleapis.com/compute'):
            raise ValueError('Invalid self_link url: %s' % params['resource_url'])
        else:
            parts = params['resource_url'].split('/')[8:]
            if len(parts) == 2:
                resource_type, resource_name = parts
                resource_location = 'global'
            else:
                resource_location, resource_type, resource_name = parts
    else:
        if not params['resource_type'] or not params['resource_location'] \
                or not params['resource_name']:
            raise ValueError('Missing required resource params.')
        resource_type = params['resource_type'].lower()
        resource_name = params['resource_name'].lower()
        resource_location = params['resource_location'].lower()

    if resource_type not in KNOWN_RESOURCES:
        raise ValueError('Unsupported resource_type: %s' % resource_type)

    # TODO(all): See the comment above for KNOWN_RESOURCES. As labels are
    # added to the v1 GCE API for more resources, some minor code work will
    # need to be added here.
    if resource_type == 'instances':
        resource = client.instances().get(project=params['project_id'],
                                          zone=resource_location,
                                          instance=resource_name).execute()
    elif resource_type == 'disks':
        resource = client.disks().get(project=params['project_id'],
                                      zone=resource_location,
                                      disk=resource_name).execute()
    elif resource_type == 'snapshots':
        resource = client.snapshots().get(project=params['project_id'],
                                          snapshot=resource_name).execute()
    elif resource_type == 'images':
        resource = client.images().get(project=params['project_id'],
                                       image=resource_name).execute()
    else:
        raise ValueError('Unsupported resource type: %s' % resource_type)

    return {
        'resource_name': resource.get('name'),
        'resource_url': resource.get('selfLink'),
        'resource_type': resource_type,
        'resource_location': resource_location,
        'label_fingerprint': resource.get('labelFingerprint'),
        'labels': resource.get('labels')
    }


def _set_labels(client, ri, params):
    result = err = None
    labels = {
        'labels': params['labels'],
        'labelFingerprint': ri['label_fingerprint']
    }

    # TODO(all): See the comment above for KNOWN_RESOURCES. As labels are
    # added to the v1 GCE API for more resources, some minor code work will
    # need to be added here.
    if ri['resource_type'] == 'instances':
        req = client.instances().setLabels(project=params['project_id'],
                                           instance=ri['resource_name'],
                                           zone=ri['resource_location'],
                                           body=labels)
    elif ri['resource_type'] == 'disks':
        req = client.disks().setLabels(project=params['project_id'],
                                       zone=ri['resource_location'],
                                       resource=ri['resource_name'],
                                       body=labels)
    elif ri['resource_type'] == 'snapshots':
        req = client.snapshots().setLabels(project=params['project_id'],
                                           resource=ri['resource_name'],
                                           body=labels)
    elif ri['resource_type'] == 'images':
        req = client.images().setLabels(project=params['project_id'],
                                        resource=ri['resource_name'],
                                        body=labels)
    else:
        raise ValueError('Unsupported resource type: %s' % ri['resource_type'])

    # TODO(erjohnso): Once Labels goes GA, we'll be able to use the GCPUtils
    # method to poll for the async request/operation to complete before
    # returning. However, during 'beta', we are in an odd state where
    # API requests must be sent to the 'compute/beta' API, but the python
    # client library only allows for *Operations.get() requests to be
    # sent to 'compute/v1' API. The response operation is in the 'beta'
    # API-scope, but the client library cannot find the operation (404).
    # result = GCPUtils.execute_api_client_req(req, client=client, raw=False)
    # return result, err
    result = req.execute()
    return True, err


def main():
    module = AnsibleModule(argument_spec=dict(
        state=dict(choices=['absent', 'present'], default='present'),
        service_account_email=dict(),
        service_account_permissions=dict(type='list'),
        pem_file=dict(),
        credentials_file=dict(),
        labels=dict(required=False, type='dict'),
        resource_url=dict(required=False, type='str'),
        resource_name=dict(required=False, type='str'),
        resource_location=dict(required=False, type='str'),
        resource_type=dict(required=False, type='str'),
        project_id=dict(),),)

    if not HAS_PYTHON26:
        module.fail_json(
            msg="GCE module requires python's 'ast' module, python v2.6+")

    client, cparams = get_google_api_client(module, 'compute',
                                            user_agent_product=UA_PRODUCT,
                                            user_agent_version=UA_VERSION,
                                            api_version=GCE_API_VERSION)

    params = {}
    params['labels'] = module.params.get('labels', {})
    params['resource_url'] = module.params.get('resource_url')
    params['resource_type'] = module.params.get('resource_type')
    params['resource_location'] = module.params.get('resource_location')
    params['resource_name'] = module.params.get('resource_name')
    params['project_id'] = module.params.get('project_id')
    params['state'] = module.params.get('state')

    # Get current resource info including labelFingerprint
    resource_info = _fetch_resource(client, params)

    changed = False
    json_output = {'state': params['state']}

    if params['state'] == 'absent' and params['labels']:
        raise ValueError("Cannot specify labels with 'absent'.")

    changed, err = _set_labels(client, resource_info, params)

    json_output['changed'] = changed

    # TODO(erjohnso): probably want to re-fetch the resource to return the
    # new labelFingerprint, check that desired labels match updated labels.
    # BUT! Will need to wait for setLabels() to hit v1 API so we can use the
    # GCPUtils feature to poll for the operation to be complete. For now,
    # we'll just update the output with what we have from the original
    # state of the resource.
    json_output.update(resource_info)
    json_output.update(params)

    module.exit_json(**json_output)

if __name__ == '__main__':
    main()
