from __future__ import print_function

import boto3
import configparser
from jinja2 import Environment, FileSystemLoader
import json
import os


# # templateLoader = FileSystemLoader(searchpath='./src/templates', encoding='utf-8')
#
# # SLACK_TEMPLATE_FILE = "slack_channels_map.json"
#
#
#


class PipelineCreator:
    """
        Class creates new pipeline templates consumed by GoCD
    """
    defaults = {"resources_path": "resources", "queue": 'gocd-update', "pipeline_template": "vevo.json.template",
                "env_template": "vevo-gocd-env.json.template", "dockerfile": True,
                "stages": ["build", "deploy-dev", "deploy-stg", "deploy-prd"],
                "commands": ['@echo "building nothing"', '@echo "deploy-dev nothing"', '@echo "deploy-staging nothing"',
                             '@echo "deploy-prd nothing"']}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        for key, val in kwargs.items():
            setattr(self, key, val)

        self._slack_channels_map = {}
        # with open(os.path.join(os.path.dirname(__file__), "slack_channels_map.json"), "r") as f:
        #     self._slack_channels_map = json.loads(f.read())

        self.templateLoader = FileSystemLoader(searchpath='./templates', encoding='utf-8')
        self.env = Environment(loader=self.templateLoader, trim_blocks=True)
        self.env.filters['jsonify'] = json.dumps

        self.template_pipe = self.env.get_template(PipelineCreator.defaults["pipeline_template"])
        self.template_env = self.env.get_template(PipelineCreator.defaults["env_template"])

    def __getattr__(self, key):
        try:
            return PipelineCreator.defaults[key]
        except KeyError:
            raise AttributeError(f"Don't recognize {key}")



    def create_default_makefile(self):
        """
        :param path: to the temp directory
        """
        try:
            with open(os.path.join(self.path, 'Makefile'), 'w') as makefile:
                print("DC=docker-compose\nSLACK_NOTIFY=$(DC) -f docker-compose.slack.yml run --rm\n", file=makefile)
                for f1, f2 in zip(PipelineCreator.defaults['stages'], PipelineCreator.defaults['commands']):
                        print(f1, f2, sep=':\n\t', end='\n\n', file=makefile)
                print("slack_success:\n\t$(SLACK_NOTIFY) success\n", file=makefile)
                print("slack_failure:\n\t$(SLACK_NOTIFY) failure\n", file=makefile)

        except IOError as e:
            print('IOError')
            print(e)

    def create_docker_compose_slack(self):
        """
        :param path: to the temp directory
        """
        try:
            with open(os.path.join(self.path, 'docker-compose.slack.yml'), 'w') as dc:
                print("""version: '2'
services:
  slack_notify:
    image: vevo/slack-notify:$SLACK_NOTIFY_VERSION
    environment:
      GO_PIPELINE_NAME: $GO_PIPELINE_NAME
      GO_STAGE_NAME: $GO_STAGE_NAME
      GO_JOB_NAME: $GO_JOB_NAME
      GO_PIPELINE_COUNTER: $GO_PIPELINE_COUNTER
      GO_TO_REVISION: $GO_TO_REVISION
    volumes:
      - .:/repos

  success:
    extends:
      service: slack_notify
    environment:
      SUCCESS: "true"
      SLACK_CHANNELS: $SLACK_CHANNELS_SUCCESS

  failure:
    extends:
      service: slack_notify
    environment:
      SUCCESS: "false"
      SLACK_CHANNELS: $SLACK_CHANNELS_FAILURE""", file=dc)

        except IOError as e:
            print('IOError')
            print(e)

    @staticmethod
    def create_resource_dir(path):
        """
            Keeping all pipeline related files in resources directory
        :param path: working temp directory + resources path
        :return:
        """
        os.makedirs(path)
        return path

    def get_slack_channels_for_team(self, team_name):
        slack_channels_success = ''
        slack_channels_failure = ''

        if team_name not in self._slack_channels_map:
            print("WARNING: team {} not found in slack channels mapping, will default to blank string".format(team_name))
        else:
            slack_channels_success = self._slack_channels_map[team_name]['success']
            if len(slack_channels_success) == 0:
                print("WARNING: team {}'s slack channels for success notification is an empty string".format(team_name))
            slack_channels_failure = self._slack_channels_map[team_name]['failure']
            if len(slack_channels_failure) == 0:
                print("WARNING: team {}'s slack channels for failure notification is an empty string".format(team_name))

        return (slack_channels_success, slack_channels_failure)

    def create_file(self, data, file_end, used_env='json-env'):
        with open(f'{PipelineCreator.defaults["resources_path"]}/{used_env}.{file_end}', 'w') as f:
            # template = data
            # self.template_env.render(used_env=used_env, pipeline_name=pipe_name)
            f.write(self.template_env.render(used_env=used_env, pipeline_name=self.pipeline_name))

    def create_pipeline_file(self, pipeline_name, team_name, resource_path):
        """
        :param pipeline_name: string
        :param team_name: string
        :param resource_path: path
        :return: resource_path, pipeline_name
        """
        # slack_channels_success, slack_channels_failure = self.get_slack_channels_for_team(self.pipe_args)

        # if team_name not in self._slack_channels_map:
        #     print("WARNING: team {} not found in slack channels mapping, will default to blank string".format(team_name))
        # else:
        #     slack_channels_success = self._slack_channels_map[team_name]['success']
        #     if len(slack_channels_success) == 0:
        #         print("")

        try:
            self.create_file()
            # with open(f'{resource_path}/{self.pipeline_name}.gopipeline.json', 'w') as f:
            #     f.write(self.template_pipe.render(pipeline_name=pipeline_name, group=team_name, stages=self._stages))
            #             # slack_channels_success=slack_channels_success, slack_channels_failure=slack_channels_failure))
        except Exception as e:
            print(f'[!] ERROR:{e}')
            print(f'[-] FAILED. Could not create {self.pipeline_name}')

    # def create_env_file(self, resource_path, pipe_name, file_end = 'goenvironment.json', used_env='json-env'):
    #     self.create_file()
    #     """
    #     :param resource_path: string
    #     :param pipe_name: string
    #     :param used_env: GoCD env for the pipeline
    #     """
    #     # self.env.filters['jsonify'] = json.dumps
    #     PipelineCreator.create_file()
    #     # with open(f'{resource_path}/{used_env}.goenvironment.json', 'w') as f:
    #     #     f.write(self.template_env.render(used_env=used_env, pipeline_name=pipe_name))





    def create_pipeline(self):
        self.create_default_makefile()
        self.create_docker_compose_slack()
        self.create_pipeline_file(self.pipeline_name, self.pipe_args, PipelineCreator.create_resource_dir(os.path.join(self.path, PipelineCreator.defaults['resources_path'])))

    @staticmethod
    def connect():
        """
        :return: aws connection
        """
        sqs = boto3.resource('sqs', region_name='us-east-1')
        q = sqs.get_queue_by_name(QueueName=PipelineCreator.defaults['queue'])
        return q

    def gocd_notifier(self):
        """
           Sending the project name to the sqs queue
        """
        notify_queue = PipelineCreator.connect()
        try:
            notify_queue.send_message(MessageBody=self.pipeline_name, )
        except Exception as e:
            print(f'Unable to send sqs queue {notify_queue}\nERROR: {e}')
