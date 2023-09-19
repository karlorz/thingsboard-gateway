from os.path import exists, splitext
from os import path
from re import IGNORECASE, compile
from json import load, dump

from questionary import Validator, ValidationError, prompt
from pyfiglet import Figlet
from termcolor import colored
from yaml import safe_load


if exists('thingsboard_gateway/config/tb_gateway.json'):
    CONFIG_PATH = 'thingsboard_gateway/config/tb_gateway.json'
elif exists(path.dirname(path.abspath(__file__)) + '/config/tb_gateway.json'.replace('/', path.sep)):
    CONFIG_PATH = path.dirname(path.abspath(__file__)) + '/config/tb_gateway.json'.replace('/', path.sep)
elif exists("/etc/thingsboard-gateway/config/tb_gateway.json".replace('/', path.sep)):
    CONFIG_PATH = "/etc/thingsboard-gateway/config/tb_gateway.json".replace('/', path.sep)
elif exists('thingsboard_gateway/config/tb_gateway.yaml'):
    CONFIG_PATH = 'thingsboard_gateway/config/tb_gateway.yaml'
elif exists(path.dirname(path.abspath(__file__)) + '/config/tb_gateway.yaml'.replace('/', path.sep)):
    CONFIG_PATH = path.dirname(path.abspath(__file__)) + '/config/tb_gateway.yaml'.replace('/', path.sep)
elif exists("/etc/thingsboard-gateway/config/tb_gateway.yaml".replace('/', path.sep)):
    CONFIG_PATH = "/etc/thingsboard-gateway/config/tb_gateway.yaml".replace('/', path.sep)

class NotNullValidator(Validator):
    def validate(self, document):
        if not document.text or document.text == '':
            raise ValidationError(message='Value can be empty!', cursor_position=len(document.text))


class NumberValidator(Validator):
    def validate(self, document):
        try:
            int(document.text)
        except ValueError:
            raise ValidationError(message='Must be a number type!', cursor_position=len(document.text))


class PortValidator(Validator):
    def validate(self, document):
        try:
            port = int(document.text)
        except ValueError:
            raise ValidationError(message='Must be a number type!', cursor_position=len(document.text))

        if not 1 <= port <= 65535:
            raise ValidationError(message='Port is invalid!', cursor_position=len(document.text))


class HostValidator(NotNullValidator):
    def validate(self, document):
        super(HostValidator, self).validate(document)

        hostname = document.text
        if len(hostname) > 255:
            return ValidationError(message='Host is invalid!', cursor_position=len(document.text))

        if hostname[-1] == ".":
            hostname = hostname[:-1]

        allowed = compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", IGNORECASE)
        if not all(allowed.match(x) for x in hostname.split(".")):
            raise ValidationError(message='Host is invalid!', cursor_position=len(document.text))


class PathValidator(Validator):
    def validate(self, document):
        if not exists(document.text):
            raise ValidationError(message='File doesn\'t exist!', cursor_position=len(document.text))

        if splitext(document.text)[1] != '.pem':
            raise ValidationError(message='File must be .pem extension!', cursor_position=len(document.text))


class FileExtensionValidator(NotNullValidator):
    def validate(self, document):
        super(FileExtensionValidator, self).validate(document)

        if document.text.split('.')[-1] != 'json':
            raise ValidationError(message='File must be .json!', cursor_position=len(document.text))


def read_config_file() -> {str: str}:
    file_extension = CONFIG_PATH.split('.')[-1]
    if file_extension == 'json':
        try:
            with open(CONFIG_PATH, 'r') as file:
                config_dict = load(file)
        except Exception as e:
            print('Failed to load configuration file:\n %s', e)
    else:
        print('YAML configuration is deprecated. '
                    'Please, use JSON configuration instead.')
        print(
            'See default configuration on '
            'https://thingsboard.io/docs/iot-gateway/configuration/?storageConfig=sqlite#storage-configuration')
        try:
            with open(CONFIG_PATH, 'r') as general_config:
                config_dict = safe_load(general_config)
        except Exception as e:
            print('Failed to load configuration file:\n %s', e)

    return config_dict


def generate_config_file(data: {str: str}) -> None:
    config_path = CONFIG_PATH
    if CONFIG_PATH.split('.')[-1] == 'yaml':
        config_path = ''.join(CONFIG_PATH.split('.')[:-1]) + '.json'

    with open(config_path, 'w') as file:
        dump(data, file, sort_keys=False, indent='  ')


def configure():
    try:
        default_config = read_config_file()
        connectors_list = []
        grpc_enabled = False
        base_answers = default_config['thingsboard']
        statistics_answers = default_config['thingsboard'].get('statistics', {})
        grpc_api_answers = default_config.get('grpc', {})
        storage_answers = default_config.get('storage', {})
        qos_and_storage_type_answers = {
            'qos': 1,
            'storage': 'memory'
        }

        # GENERAL SETTINGS ---------------------------------------------------------------------------------------------
        simple_setup_questions = [
            {
                'type': 'input',
                'name': 'host',
                'message': 'ThingsBoard host:',
                'default': default_config['thingsboard']['host'],
                'validate': HostValidator
            },
            {
                'type': 'input',
                'name': 'port',
                'message': 'ThingsBoard port:',
                'default': str(default_config['thingsboard']['port']),
                'validate': PortValidator,
                'filter': lambda val: int(val)
            },
            {
                'type': 'confirm',
                'name': 'remoteConfiguration',
                'message': 'Do you want to enable remote configuration feature? (No)',
                'default': False
            },
            {
                'type': 'list',
                'name': 'security',
                'message': 'What security type do you need?',
                'choices': [
                    'Access Token (Basic Security)',
                    'Username and Password (Basic Security)',
                    'TLS + Access Token (Advanced Security)',
                    'TLS + Private Key (Advanced Security)'
                ]
            }
        ]

        base_questions = [
            {
                'type': 'confirm',
                'name': 'remoteShell',
                'message': 'Do you want to have access from remote shell? (No)',
                'default': False
            },
            {
                'type': 'input',
                'name': 'minPackSendDelayMS',
                'message': 'Minimal delay between sending messages (milliseconds):',
                'default': str(default_config['thingsboard']['minPackSendDelayMS']),
                'validate': NumberValidator,
                'filter': lambda val: int(val)
            },
            {
                'type': 'input',
                'name': 'maxPayloadSizeBytes',
                'message': 'Maximum payload size (bytes):',
                'default': str(default_config['thingsboard']['maxPayloadSizeBytes']),
                'validate': NumberValidator,
                'filter': lambda val: int(val)
            },
            {
                'type': 'input',
                'name': 'minPackSizeToSend',
                'message': 'Minimal pack size for sending (bytes):',
                'default': str(default_config['thingsboard']['minPackSizeToSend']),
                'validate': NumberValidator,
                'filter': lambda val: int(val)
            },
            {
                'type': 'confirm',
                'name': 'handleDeviceRenaming',
                'message': 'Handle device renaming?',
                'default': bool(default_config['thingsboard']['handleDeviceRenaming']),
            },
            {
                'type': 'input',
                'name': 'checkConnectorsConfigurationInSeconds',
                'message': 'Connectors config files will check every (sec.):',
                'default': str(default_config['thingsboard']['checkConnectorsConfigurationInSeconds']),
                'validate': NumberValidator,
                'filter': lambda val: int(val)
            },
            {
                'type': 'confirm',
                'name': 'grpc-enabled',
                'message': 'Do you want to enable GRPC API on your gateway?',
                'default': False
            },
            {
                'type': 'confirm',
                'name': 'statistics-enabled',
                'message': 'Do you want to enable statistics collecting?',
                'default': True
            }
        ]

        f = Figlet(font='slant')
        print(colored(f.renderText('ThingsBoard'), color='white'))
        print(colored(f.renderText('IoT Gateway'), color='red'))
        print(colored('Welcome to ThingsBoard IoT Gateway configuration Wizard', 'cyan'))
        print(colored('Let\'s configure you Gateway by answering on questions below ⬇\n'))

        simple_setup_answers = prompt(simple_setup_questions)

        # SECURITY SETTINGS --------------------------------------------------------------------------------------------
        access_token_config = [
            {
                'type': 'input',
                'name': 'accessToken',
                'message': 'Your token:',
                'validate': NotNullValidator
            }
        ]
        tls = [
            {
                'type': 'input',
                'name': 'caCert',
                'message': 'Path to your CA file (.pem):',
                'validate': PathValidator
            }
        ]
        basic_config = [
            {
                'type': 'input',
                'name': 'username',
                'message': 'Your username:'
            },
            {
                'type': 'input',
                'name': 'password',
                'message': 'Your password:'
            },
            {
                'type': 'input',
                'name': 'clientId',
                'message': 'Your client ID:'
            }
        ]
        tls_access_token_config = access_token_config + tls
        tls_private_key_config = [
                                     {
                                         'type': 'input',
                                         'name': 'privateKey',
                                         'message': 'Path to you private key file (.pem):',
                                         'validate': PathValidator
                                     }
                                 ] + tls + [
                                     {
                                         'type': 'input',
                                         'name': 'cert',
                                         'message': 'Path to your certificate file (.pem):',
                                         'validate': PathValidator
                                     }
                                 ]

        if simple_setup_answers['security'] == 'Access Token (Basic Security)':
            security_questions = access_token_config
        elif simple_setup_answers['security'] == 'TLS + Access Token (Advanced Security)':
            security_questions = tls_access_token_config
        elif simple_setup_answers['security'] == 'Username and Password (Basic Security)':
            security_questions = basic_config
        else:
            security_questions = tls_private_key_config

        security_answers = prompt(security_questions)

        continue_answer = prompt([
            {
                'type': 'confirm',
                'name': 'continue',
                'message': 'Continue to advance settings?'
            }
        ])

        if continue_answer['continue']:
            base_answers = prompt(base_questions)

            # STATISTICS SETTINGS --------------------------------------------------------------------------------------
            statistics_answers = {}
            if base_answers.pop('statistics-enabled'):
                statistics_config = [
                    {
                        'type': 'input',
                        'name': 'statsSendPeriodInSeconds',
                        'message': 'Period of time sending statistics (sec.):',
                        'default': str(default_config['thingsboard']['statistics']['statsSendPeriodInSeconds']),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'type': 'input',
                        'name': 'configuration',
                        'message': 'Config file of custom statistic commands:'
                    }
                ]

                statistics_answers = prompt(statistics_config)
                statistics_answers['enable'] = True

            # GRPC SETTINGS ------------------------------------------------------------------------------------------------
            grpc_enabled = base_answers.pop('grpc-enabled')

            if grpc_enabled:
                grpc_api_questions = [
                    {
                        'name': 'serverPort',
                        'default': 9595,
                        'message': '[GRPC] Please set port for GRPC server:',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'name': 'keepaliveTimeMs',
                        'default': 10000,
                        'message': '[GRPC] Keep alive period:',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'name': 'keepaliveTimeoutMs',
                        'default': 5000,
                        'message': '[GRPC] Keep alive timeout',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'name': 'keepalivePermitWithoutCalls',
                        'default': True,
                        'message': '[GRPC] Allow send pings from clients without calls:'
                    },
                    {
                        'name': 'maxPingsWithoutData',
                        'default': 0,
                        'message': '[GRPC] Maximal count of pings without data from client to server:',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'name': 'minTimeBetweenPingsMs',
                        'default': 10000,
                        'message': '[GRPC] Minimal period between ping messages:',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'name': 'minPingIntervalWithoutDataMs',
                        'default': 5000,
                        'message': '[GRPC] Minimal period between ping messages without data:',
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                ]
                grpc_api_answers = prompt(grpc_api_questions)
            else:
                grpc_api_answers = default_config.get('grpc', {})

            # QOS AND STORAGE TYPE SETTINGS ----------------------------------------------------------------------------
            qos_and_storage_type_question = [
                {
                    'type': 'input',
                    'name': 'qos',
                    'message': 'QoS:',
                    'validate': NumberValidator,
                    'default': str(default_config['thingsboard']['qos']),
                    'filter': lambda val: int(val)
                },
                {
                    'type': 'list',
                    'name': 'storage',
                    'message': 'Choose storage type:',
                    'choices': [
                        'Memory',
                        'File storage',
                        'SQLite'
                    ],
                    'filter': lambda val: 'file' if val == 'File storage' else val.lower()
                }
            ]

            qos_and_storage_type_answers = prompt(qos_and_storage_type_question)

            # STORAGE SETTINGS -----------------------------------------------------------------------------------------
            if qos_and_storage_type_answers['storage'] == 'memory':
                storage_questions = [
                    {
                        'type': 'input',
                        'name': 'read_records_count',
                        'message': 'Count of messages to get from storage and send to ThingsBoard:',
                        'default': str(default_config['storage'].get('read_records_count', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'type': 'input',
                        'name': 'max_records_count',
                        'message': 'Maximum count of data in storage before send to ThingsBoard:',
                        'default': str(default_config['storage'].get('max_records_count', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    }
                ]
            elif qos_and_storage_type_answers['storage'] == 'file':
                storage_questions = [
                    {
                        'type': 'input',
                        'name': 'data_folder_path',
                        'message': 'Path to folder, that will contains data (Relative or Absolute):',
                        'default': str(default_config['storage'].get('data_folder_path', '')),
                        'validate': NotNullValidator
                    },
                    {
                        'type': 'input',
                        'name': 'max_file_count',
                        'message': 'Maximum count of file that will be saved:',
                        'default': str(default_config['storage'].get('max_file_count', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'type': 'input',
                        'name': 'max_read_records_count',
                        'message': 'Count of messages to get from storage and send to ThingsBoard:',
                        'default': str(default_config['storage'].get('max_read_records_count', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'type': 'input',
                        'name': 'max_records_per_file',
                        'message': 'Maximum count of records that will be stored in one file:',
                        'default': str(default_config['storage'].get('max_records_per_file', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    }
                ]
            else:
                storage_questions = [
                    {
                        'type': 'input',
                        'name': 'data_file_path',
                        'message': 'Path to folder, that will contains data (Relative or Absolute):',
                        'default': str(default_config['storage'].get('data_file_path', '')),
                        'validate': NotNullValidator
                    },
                    {
                        'type': 'input',
                        'name': 'messages_ttl_check_in_hours',
                        'message': 'How often will Gateway check data for obsolescence:',
                        'default': str(default_config['storage'].get('messages_ttl_check_in_hours', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    },
                    {
                        'type': 'input',
                        'name': 'messages_ttl_in_days',
                        'message': 'Maximum days that storage will save data:',
                        'default': str(default_config['storage'].get('messages_ttl_in_days', '')),
                        'validate': NumberValidator,
                        'filter': lambda val: int(val)
                    }
                ]

            storage_answers = prompt(storage_questions)

            # CONNECTORS SETTINGS --------------------------------------------------------------------------------------
            connectors_questions = [
                {
                    'type': 'checkbox',
                    'name': 'connectors',
                    'message': 'Choose connectors you want to use:',
                    'choices': [
                        {
                            'name': 'MQTT',
                        },
                        {
                            'name': 'FTP',
                        },
                        {
                            'name': 'Modbus',
                        },
                        {
                            'name': 'CAN',
                        },
                        {
                            'name': 'Bacnet',
                        },
                        {
                            'name': 'BLE',
                        },
                        {
                            'name': 'OPC-UA',
                        },
                        {
                            'name': 'OPC-UA AsyncIO'
                        },
                        {
                            'name': 'ODBC',
                        },
                        {
                            'name': 'Request',
                        },
                        {
                            'name': 'REST',
                        },
                        {
                            'name': 'SNMP'
                        },
                        {
                            'name': 'XMPP'
                        },
                        {
                            'name': 'OCPP'
                        },
                        {
                            'name': 'Socket'
                        }
                    ],
                    'validate': lambda answer: 'You must choose at least one connector.' if len(answer) == 0 else True
                }
            ]

            connectors_answers = prompt(connectors_questions)

            for connector in connectors_answers['connectors']:
                print(colored(f'Configuration {connector} connector:', 'blue'))
                connector_questions = [
                    {
                        'type': 'input',
                        'name': 'name',
                        'message': 'Name of connector:',
                        'validate': NotNullValidator
                    },
                    {
                        'type': 'input',
                        'name': 'configuration',
                        'message': 'Config file of connector:',
                        'validate': FileExtensionValidator
                    }
                ]
                connector_answers = prompt(connector_questions)
                connectors_list.append({'type': connector.lower(), **connector_answers})

        generate_config_file(
            {
                'thingsboard': {**base_answers, **simple_setup_answers, 'security': security_answers,
                                'qos': qos_and_storage_type_answers['qos'], 'statistics': statistics_answers},
                'storage': {'type': qos_and_storage_type_answers['storage'], **storage_answers},
                'grpc': {'enabled': grpc_enabled, **grpc_api_answers},
                'connectors': connectors_list
            })
    except Exception as e:
        print(colored('Something went wrong! Please try again.', color='red'))
        raise e


if __name__ == '__main__':
    configure()
