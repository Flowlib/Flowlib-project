# -*- coding: utf-8 -*-
from abc import ABC

from nipyapi.nifi.models.processor_config_dto import ProcessorConfigDTO
from nipyapi.nifi.models.controller_service_dto import ControllerServiceDTO
from nipyapi.nifi.models.reporting_task_dto import ReportingTaskDTO

PG_NAME_DELIMETER = '/'

class FlowLibException(Exception):
    pass

class Flow:
    # TODO: Add flow_source attr which is a file:///path/to/flow.yaml or https://flow.yaml or https://nifi-api ?
    def __init__(self):
        """
        The Flow model. Do not use this constructor directly, instead use flowlib.api.new_flow()
        :param name: The name of the Flow
        :type name: str
        :param flowlib_version: The current version of the flowlib library
        :type flowlib_version: str
        :param version: The version of the Flow
        :type version: str
        :param controllers: The root controllers for the root canvas
        :type controllers: dict(str:Controller)
        :param canvas: The root elements of the flow
        :type canvas: list(FlowElement)
        :param raw: The raw yaml text of the flow.yaml
        :type raw: io.TextIOWrapper
        :param component_dir: The path to the directory containing reuseable flow components
        :type component_dir: str
        :param loaded_components: A map of components (component_ref) loaded while initializing the flow, these are re-useable components
        :type loaded_components: dict(str:FlowComponent)
        :elements: A map of elements defining the flow logic, may be deeply nested if the FlowElement is a ProcessGroup itself.
          Initialized by calling flow.init()
        :type elements: dict(str:FlowElement)
        """
        self.name = None
        self.flowlib_version = None
        self.version = None
        self.controllers = None
        self.canvas = None
        self.component_dir = None
        self.comments = None
        self.globals = None
        self.raw = None
        self.loaded_components = dict()
        self.elements = dict()

    def __repr__(self):
        return str(vars(self))

    def find_controller_by_name(self, name):
        """
        A helper method for looking up a controller by name
        :param name: The name of the controller
        :type name: str
        """
        return list(filter(lambda c: c.name == name, self.controllers))[0]

    # TODO: Unit test this
    def get_parent_element(self, element):
        """
        A helper method for looking up parent elements from a breadcrumb path
        :param element: The element to retrieve the parent of
        :type element: FlowElement
        """
        target = self
        names = element.parent_path.split(PG_NAME_DELIMETER)
        for n in names[1:]:
            elements = target.elements
            target = elements.get(n)
        return target


class FlowComponent:
    def __init__(self, component_name, source_file, process_group, raw, defaults=dict(), required_controllers=dict(), required_vars=[]):
        """
        A reuseable component of a flow. Referenced by a ProcessGroup which is an instantiation of a FlowComponent
        """
        self.component_name = component_name
        self.source_file = source_file
        self.defaults = defaults
        self.required_controllers = required_controllers
        self.required_vars = required_vars
        self.process_group = process_group
        self.raw = raw

    def __repr__(self):
        return str(vars(self))


class FlowElement(ABC):
    """
    An abstract parent class for things that might appear on the flow's canvas
    This is either a ProcessGroup, Processor, InputPort, or OutputPort
    """
    def __init__(self, name, parent_path, _type, connections):
        self._id = None
        self._parent_id = None
        self.name = name
        self.parent_path = parent_path
        self._type = _type
        self.connections

    @staticmethod
    def from_dict(elem_dict):
        if not isinstance(elem_dict, dict) or not elem_dict.get('type'):
            raise FlowLibException("FlowElement.from_dict() requires a dict with a 'type' field, one of ['processor', 'process_group', 'input_port', 'output_port']")

        name = elem_dict.get('name')
        if not name or len(name) < 1:
            raise FlowLibException("Element names may not be empty. Found invalid element with parent path: {}".format(elem_dict.get('parent_path')))
        if PG_NAME_DELIMETER in name:
            raise FlowLibException("Invalid element: '{}'. Element names may not contain '{}' characters".format(name, Flow.PG_DELIMETER))

        elem_dict['_type'] = elem_dict.pop('type')
        if elem_dict.get('_type') == 'process_group':
            if elem_dict.get('vars'):
                elem_dict['_vars'] = elem_dict.pop('vars')
            return ProcessGroup(**elem_dict)
        elif elem_dict.get('_type') == 'processor':
            return Processor(**elem_dict)
        elif elem_dict.get('_type') == 'input_port':
            return InputPort(**elem_dict)
        elif elem_dict.get('_type') == 'output_port':
            return OutputPort(**elem_dict)
        else:
            raise FlowLibException("Element 'type' field must be one of ['processor', 'process_group', 'input_port', 'output_port']")

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, _id):
        if self._parent_id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._parent_id = _id

    @property
    def type(self):
        return self._type

    def __repr__(self):
        return str(vars(self))


class ProcessGroup(FlowElement):
    def __init__(self, name, parent_path, _type, component_ref, controllers=dict(), _vars=None, connections=None):
        """
        :elements: A map of elements defining the flow logic, may be deeply nested if the FlowElement is a ProcessGroup itself.
          Initialized by calling FlowElement.load()
        :type elements: dict(str:FlowElement)
        """
        self._id = None
        self._parent_id = None
        self.name = name
        self.parent_path = parent_path
        self._type = _type
        self.component_ref = component_ref
        self.controllers = controllers
        self.vars = _vars
        self.connections = [Connection(**c) for c in connections] if connections else None
        self.elements = dict()


class Processor(FlowElement):
    def __init__(self, name, parent_path, _type, config, connections=None):
        self._id = None
        self._parent_id = None
        self.name = name
        self.parent_path = parent_path
        self._type = _type

        if not 'properties' in config:
            config['properties'] = dict()
        self.config = ProcessorConfig(config.pop('package_id'), **config)
        self.connections = [Connection(**c) for c in connections] if connections else None


class ProcessorConfig(ProcessorConfigDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))


class InputPort(FlowElement):
    def __init__(self, name, parent_path, _type, connections=None):
        self._id = None
        self._parent_id = None
        self.name = name
        self.parent_path = parent_path
        self._type = _type
        self.connections = [Connection(**c) for c in connections] if connections else None


class OutputPort(FlowElement):
    def __init__(self, name, parent_path, _type, connections=None):
        self._id = None
        self._parent_id = None
        self.name = name
        self.parent_path = parent_path
        self._type = _type
        self.connections = [Connection(**c) for c in connections] if connections else None


class Connection:
    def __init__(self, name, from_port=None, to_port=None, relationships=None):
        self.name = name
        self.from_port = from_port
        self.to_port = to_port
        self.relationships = relationships

    def __repr__(self):
        return str(vars(self))


class Controller:
    def __init__(self, name, config):
        self._id = None
        self._parent_id = None
        self.name = name

        if not 'properties' in config:
            config['properties'] = dict()
        self.config = ControllerServiceConfig(config.pop('package_id'), **config)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, _id):
        if self._parent_id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._parent_id = _id

    def __repr__(self):
        return str(vars(self))


class ControllerServiceConfig(ControllerServiceDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))


class ReportingTask:
    def __init__(self, name, config):
        self._id = None
        self.name = name

        if not 'properties' in config:
            config['properties'] = dict()
        self.config = ReportingTaskConfig(config.pop('package_id'), **config)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    def __repr__(self):
        return str(vars(self))


class ReportingTaskConfig(ReportingTaskDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))
