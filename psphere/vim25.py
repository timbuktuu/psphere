# Copyright 2010 Jonathan Kinred <jonathan.kinred@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time
from psphere.soap import VimSoap, Property

#import logging
#logging.basicConfig(level=logging.INFO)
#logging.getLogger('suds.client').setLevel(logging.DEBUG)
#logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)

class ManagedObjectReference(Property):
    """Custom class to replace the suds generated class, which lacks _type."""
    def __init__(self, mor=None, type=None, value=None):
        if mor:
            Property.__init__(self, mor.value)
            self._type = str(mor._type)
        else:
            Property.__init__(self, value)
            self._type = str(type)

class Vim(object):
    def __init__(self, url, username, password):
        self.vsoap = VimSoap(url)
        self.service_instance = ServiceInstance(vim=self)
        self.vsoap.invoke('Login',
                         _this=self.service_instance.content.sessionManager,
                         userName=username, password=password)

    def get_entity(self, mor, properties=None):
        """Retrieve the properties of a single managed object.
        Arguments:
            mor: ManagedObjectReference of the object to retrieve.
            properties: The properties to retrieve from the managed object.
        Returns:
            A view of the 
        """

        entity = eval(str(mor._type))(mor=mor, vim=self)
        return entity

    def get_entities(self, mors, properties=None):
        property_spec = self.vsoap.create_object('PropertySpec')
        property_spec.all = True
        property_spec.type = str(mors[0]._type)

        object_specs = []
        for mor in mors:
            object_spec = self.vsoap.create_object('ObjectSpec')
            object_spec.obj = mor
            object_specs.append(object_spec)

        pfs = self.vsoap.create_object('PropertyFilterSpec')
        pfs.propSet = [property_spec]
        pfs.objectSet = object_specs

        pc_mor = self.service_instance.content.propertyCollector
        property_collector = PropertyCollector(mor=pc_mor, vim=self)
        obj_contents = property_collector.retrieve_properties(spec_set=pfs)

        entities = []
        for obj_content in obj_contents:
            entity = eval(str(obj_content.obj._type))(mor=obj_content.obj,
                                                      vim=self)
            entities.append(entity)

        return entities
        
    def get_property_spec(self):
        """Return a PropertySpec for matching the class this is called from."""
        property_spec = self.vim.vsoap.create_object('PropertySpec')
        property_spec.all = True
        property_spec.type = self.mor._type

        return property_spec
    def get_search_filter_spec(self, begin_entity, property_spec):
        """Build a PropertyFilterSpec capable of full inventory traversal.
        
        By specifying all valid traversal specs we are creating a PFS that
        can recursively select any object under the given enitity.

        """
        # The selection spec for additional objects we want to filter
        ss_strings = ['resource_pool_traversal_spec',
                      'resource_pool_vm_traversal_spec',
                      'folder_traversal_spec',
                      'datacenter_host_traversal_spec',
                      'datacenter_vm_traversal_spec',
                      'compute_resource_rp_traversal_spec',
                      'compute_resource_host_traversal_spec',
                      'host_vm_traversal_spec']

        # Create a selection spec for each of the strings specified above
        selection_specs = []
        for ss_string in ss_strings:
            selection_spec = self.vsoap.create_object('SelectionSpec')
            selection_spec.name = ss_string
            selection_specs.append(selection_spec)

        # A traversal spec for deriving ResourcePool's from found VMs
        rpts = self.vsoap.create_object('TraversalSpec')
        rpts.name = 'resource_pool_traversal_spec'
        rpts.type = 'ResourcePool'
        rpts.path = 'resourcePool'
        rpts.selectSet = [selection_specs[0], selection_specs[1]]

        # A traversal spec for deriving ResourcePool's from found VMs
        rpvts = self.vsoap.create_object('TraversalSpec')
        rpvts.name = 'resource_pool_vm_traversal_spec'
        rpvts.type = 'ResourcePool'
        rpvts.path = 'vm'

        crrts = self.vsoap.create_object('TraversalSpec')
        crrts.name = 'compute_resource_rp_traversal_spec'
        crrts.type = 'ComputeResource'
        crrts.path = 'resourcePool'
        crrts.selectSet = [selection_specs[0], selection_specs[1]]

        crhts = self.vsoap.create_object('TraversalSpec')
        crhts.name = 'compute_resource_host_traversal_spec'
        crhts.type = 'ComputeResource'
        crhts.path = 'host'
         
        dhts = self.vsoap.create_object('TraversalSpec')
        dhts.name = 'datacenter_host_traversal_spec'
        dhts.type = 'Datacenter'
        dhts.path = 'hostFolder'
        dhts.selectSet = [selection_specs[2]]

        dvts = self.vsoap.create_object('TraversalSpec')
        dvts.name = 'datacenter_vm_traversal_spec'
        dvts.type = 'Datacenter'
        dvts.path = 'vmFolder'
        dvts.selectSet = [selection_specs[2]]

        hvts = self.vsoap.create_object('TraversalSpec')
        hvts.name = 'host_vm_traversal_spec'
        hvts.type = 'HostSystem'
        hvts.path = 'vm'
        hvts.selectSet = [selection_specs[2]]
      
        fts = self.vsoap.create_object('TraversalSpec')
        fts.name = 'folder_traversal_spec'
        fts.type = 'Folder'
        fts.path = 'childEntity'
        fts.selectSet = [selection_specs[2], selection_specs[3],
                          selection_specs[4], selection_specs[5],
                          selection_specs[6], selection_specs[7],
                          selection_specs[1]]

        obj_spec = self.vsoap.create_object('ObjectSpec')
        obj_spec.obj = begin_entity
        obj_spec.selectSet = [fts, dvts, dhts, crhts, crrts,
                               rpts, hvts, rpvts]

        pfs = self.vsoap.create_object('PropertyFilterSpec')
        pfs.propSet = [property_spec]
        pfs.objectSet = [obj_spec]
        return pfs

    def find_entity(self, entity_type, begin_entity=None, filter=None):
        entity_types = ['ClusterComputeResource', 'ComputeResource',
                        'Datacenter', 'Folder', 'HostSystem',
                        'ResourcePool', 'VirtualMachine']

        if entity_type not in entity_types:
            print('Invalid entity type specified.')
            return None

        # Start at the root folder if no begin_entity was specified
        if not begin_entity:
            begin_entity = self.service_instance.content.rootFolder

        property_spec = self.vsoap.create_object('PropertySpec')
        # TODO: Set all to False and set the pathSet parameter
        property_spec.all = False
        property_spec.type = entity_type
        #property_spec.pathSet = filter
        pfs = self.get_search_filter_spec(begin_entity, property_spec)
        pc_mor = self.service_instance.content.propertyCollector
        property_collector = PropertyCollector(mor=pc_mor, vim=self)
        obj_contents = property_collector.retrieve_properties(spec_set=pfs)
        entity = eval(entity_type)(mor=obj_contents[0].obj, vim=self)
        return entity

class ServiceInstance(object):
    def __init__(self, vim):
        self.vim = vim
        self.mor = ManagedObjectReference(type='ServiceInstance',
                                          value='ServiceInstance')
        self.content = self.vim.vsoap.invoke('RetrieveServiceContent',
                                             _this=self.mor)

    def current_time(self):
        return self.vim.vsoap.invoke('CurrentTime', _this=self.mor)

class ManagedObject(object):
    """The base class which all managed object's derive from."""
    def __init__(self, mor, vim):
        """vim: A reference back to the Vim object."""
        self.mor = mor
        self.vim = vim

    def get_property_filter_spec(self, mor):
        """Create a PropertyFilterSpec for matching the current class.
        
        Called from derived classes, it's a simple way of creating
        a PropertySpec that will match the type of object that the
        method is called from. It returns a List, which is what
        PropertyFilterSpec expects.

        Returns:
            A list of one PropertySpec
        """
        property_spec = self.vim.vsoap.create_object('PropertySpec')
        property_spec.all = True
        property_spec.type = self.mor._type

        object_spec = self.vim.vsoap.create_object('ObjectSpec')
        object_spec.obj = mor

        property_filter_spec = self.vim.vsoap.create_object('PropertyFilterSpec')
        property_filter_spec.propSet = [property_spec]
        property_filter_spec.objectSet = [object_spec]

        return property_filter_spec

    def update_view_data(self, properties=None):
        """Synchronise the local object with the server-side object."""
        pfs = self.get_property_filter_spec(self.mor)
        # TODO: Use the properties argument to filter relevant props
        pc_mor = self.vim.service_instance.content.propertyCollector
        property_collector = PropertyCollector(mor=pc_mor, vim=self.vim)
        obj_contents = property_collector.retrieve_properties(spec_set=pfs)
        if not obj_contents:
            # TODO: Improve error checking and reporting
            print('The view could not be updated.')
        for obj_content in obj_contents:
            self.set_view_data(obj_content, properties)

    def set_view_data(self, entity, properties):
        self.ent = entity
        props = {}
        for dyn_prop in entity.propSet:
            # Kludgy way of finding if the dyn_prop contains a collection
            prop_type = str(dyn_prop.val.__class__)[
                str(dyn_prop.val.__class__).rfind('.')+1:]

            if prop_type.startswith('Array'):
                # We assume it's a collection, the real list is
                # found in the first slot
                props[dyn_prop.name] = dyn_prop.val[0]
            else:
                props[dyn_prop.name] = dyn_prop.val

        for prop in props:

            # We're not interested in empty values
            if len(props[prop]) == 0:
                continue

            # If the property hasn't been initialised in this class
            if prop in dir(self):
                if type(prop) == 'list':
                    for item in props[prop]:
                        vars(self)[prop].append(item)
                else:
                    vars(self)[prop] = props[prop]
            else:
                print('WARNING: Skipping undefined property "%s" '
                      'with value "%s"' % (prop, props[prop]))
                    
    def wait_for_task(self, task_ref):
        """Execute a task and wait for it to complete."""
        task_view = self.vim.get_entity(mor=task_ref)
        while True:
            info = task_view.info
            if info.state.val == 'success':
                return info.result
            elif info.state.val == 'error':
                # TODO: Handle error checking properly
                fault = {}
                fault['name'] = info.error.fault
                fault['detail'] = info.error.fault
                fault['error_message'] = info.error.localizedMessage
                return fault
            else:
                print('Unknown state val')

            # TODO: Implement progresscallbackfunc
            time.sleep(2)
            task_view.update_view_data()

class ExtensibleManagedObject(ManagedObject):
    def __init__(self, mor, vim):
        # Set the properties for this object
        self.availableField = []
        self.value = []
        
        # Init the base class
        ManagedObject.__init__(self, mor, vim)

        # Sync the object data with the server
        self.update_view_data()

class ManagedEntity(ExtensibleManagedObject):
    def __init__(self, mor, vim):
        self.alarmActionsEnabled = []
        self.configIssue = []
        self.configStatus = None
        self.customValue = []
        self.declaredAlarmState = []
        self.disabledMethod = None
        self.effectiveRole = []
        self.name = None
        self.overallStatus = None
        self.parent = None
        self.permission = []
        self.recentTask = []
        self.tag = []
        self.triggeredAlarmState = []

        ExtensibleManagedObject.__init__(self, mor=mor, vim=vim)

class Folder(ManagedEntity):
    def __init__(self, mor, vim):
        self.childEntity = []
        self.childType = []

        ManagedEntity.__init__(self, mor=mor, vim=vim)

    def create_folder(self, name):
        """Create a new folder with the specified name.
        Arguments:
            name: The name of the folder to create.
        Returns:
            The newly created Folder object or None if an error was encountered.

        """
        result = self.vim.vsoap.invoke('CreateFolder', _this=self.mor,
                                       name=name)
        if not result:
            return None
        else:
            return Folder(mor=result, vim=self.vim)

class PropertyCollector(ManagedObject):
    def __init__(self, mor, vim):
        self.filter = None

        ManagedObject.__init__(self, mor=mor, vim=vim)

    def retrieve_properties(self, spec_set):
        return self.vim.vsoap.invoke('RetrieveProperties', _this=self.mor,
                                     specSet=spec_set)

class ComputeResource(ManagedEntity):
    def __init__(self, mor, vim):
        self.configurationEx = None
        self.datastore = []
        self.environmentBrowser = None
        self.host = []
        self.resourcePool = None
        self.summary = None

        ManagedEntity.__init__(self, mor, vim)

class ClusterComputeResource(ComputeResource):
    def __init__(self, mor, vim):
        self.actionHistory = []
        self.configuration = None
        self.drsFault = []
        self.drsRecommendation = []
        self.migrationHistory = []
        self.recommendation = []

        ComputeResource.__init__(self, mor, vim)

class Datacenter(ManagedEntity):
    def __init__(self, mor, vim):
        self.datastore = []
        # TODO: vSphere API 4.0
        self.datastoreFolder = None
        self.hostFolder = None
        self.network = []
        # TODO: vSphere API 4.0
        self.networkFolder = None
        self.vmFolder = None

        ManagedEntity.__init__(self, mor, vim)

    def power_on_multi_vm_task(self, vm):
        """Powers on multiple VMs in a data center.

        Arguments:
            vm:     ManagedObjectReference[] to a VirtualMachine[]
                    The virtual machines to power on.
        """

        response = self.vim.vsoap.invoke('PowerOnMultiVM_Task', vm)
        return response

    def power_on_multi_vm(self, vm):
        return self.wait_for_task(self.PowerOnMultiVM_Task(vm))

class Datastore(ManagedEntity):
    def __init__(self, mor, vim):
        self.browser = None
        self.capability = None
        self.host = []
        self.info = None
        self.summary = None
        self.vm = []

        ManagedEntity.__init__(self, mor, vim)

        def refresh_datastore(self):
            """Explicitly refreshes free-space and capacity values."""
            self.vim.vsoap.invoke('RefreshDatastore', _this=self.mor)
            # Update the view data to get the new values
            self.update_view_data()

        # vSphere API 4.0
        def refresh_datastore_storage_info(self):
            self.vim.vsoap.invoke('RefreshDatastoreStorageInfo',
                                  _this=self.mor)
            # Update the view data to get the new values
            self.update_view_data()


class VirtualMachine(ManagedEntity):
    def __init__(self, mor, vim):
        self.capability = None
        self.config = None
        self.datastore = []
        self.environmentBrowser = None
        self.guest = None
        self.guestHeartbeatStatus = None
        self.layout = None
        # TODO: vSphere API 4.0
        self.layoutEx = None
        self.network = []
        self.resourceConfig = None
        self.resourcePool = None
        self.runtime = None
        self.snapshot = None
        # TODO: vSphere API 4.0
        self.storage = None
        self.summary = None

        ManagedEntity.__init__(self, mor, vim)

    def acquire_mks_ticket(self):
        return self.vim.vsoap.invoke('AcquireMksTicket', _this=self.mor)

    def answer_vm(self, question_id, answer_choice):
        """Responds to a question that is blocking this virtual machine."""
        self.vim.vsoap.invoke('AnswerVM', _this=self.mor,
                              questionId=question_id,
                              answerChoice=answer_choice)

class HostSystem(ManagedEntity):
    def __init__(self, mor, vim):
        self.capability = None
        self.config = None
        self.configManager = None
        self.datastore = []
        self.datastoreBrowser = None
        self.hardware = None
        self.network = []
        self.runtime = None
        self.summary = None
        self.systemResources = None
        self.vm = []

        ManagedEntity.__init__(self, mor, vim)

