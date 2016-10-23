from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_rpc
from google.appengine.datastore import entity_pb
from google.appengine.ext import db


def get(keys):
    """Get LazyEntities for each datastore object corresponding to the keys in keys. keys must be
    a list of db.Key objects. Deserializing datastore objects with many properties is very slow
    (~10 ms for an entity with 170 properties). google.appengine.api.datastore.GetAsync avoids
    some of the deserialization, but not all of it. This monkey-patches a private undocumented API
    to avoid nearly all of it.

    How Datastore deserialization normally works:
    * The datastore returns a blob of bytes.
    * The datastore result is parsed into a protocol buffer object: entity_pb.EntityProto. This
      probably happens in native C/C++ code in the App Engine standard environment; see comments:
      https://github.com/GoogleCloudPlatform/gcloud-python/issues/298
    * the entity_pb.EntityProto is converted into a datastore.Entity.
    * The datastore.Entity is converted into the appropriate db.Model subclass.

    This bypasses a lot of parsing by returning the EntityProto wrapped in a LazyEntity. Its likely
    to be quite a bit faster in many cases.

    If this breaks, it probably means the internal API has changed."""

    # db.get calls db.get_async calls datastore.GetAsync
    # datastore.GetAsync then calls _GetConnection(), then Connection.async_get
    # _GetConnection returns a thread-local so it should be safe to hack it in this way
    # datastore_rpc.BaseConnection uses self.__adapter.pb_to_entity to convert the entity
    # protocol buffer into an Entity: skip that step and return a LazyEntity instead
    connection = datastore._GetConnection()
    if connection._api_version != datastore_rpc._DATASTORE_V3:
        raise Exception("Unsupported API version: " + connection._api_version)
    # patch the connection because it is thread-local. Previously we patched adapter.pb_to_entity
    # which is shared. This caused exceptions in other threads under load. Oops.
    real_adapter = connection._BaseConnection__adapter
    wrapped_adapter = DatastoreLazyEntityAdapter(real_adapter)
    connection._BaseConnection__adapter = wrapped_adapter
    try:
        rpc = datastore.GetAsync(keys)
        return rpc.get_result()
    finally:
        connection._BaseConnection__adapter = real_adapter


class DatastoreLazyEntityAdapter(object):
    '''Wraps an existing datastore_rpc.AbstractAdapter and replaces pb_to_entity with a version
    that returns LazyEntity instances.'''

    def __init__(self, real_adapter):
        self.__real_adapter = real_adapter

    def pb_to_key(self, pb):
        return self.__real_adapter.pb_to_key(pb)

    def pb_to_entity(self, pb):
        return LazyEntity(pb)

    def key_to_pb(self, key):
        return self.__real_adapter.key_to_pb(key)

    def entity_to_pb(self, entity):
        return self.__real_adapter.entity_to_pb(entity)

    def pb_to_index(self, pb):
        return self.__real_adapter.pb_to_index(pb)


class LazyEntity(object):
    """Wraps an entity_pb.EntityProto to provide easy access to properties. It caches the
    conversion from property to Python because accessing protocol buffer properties is slower
    than accessing native Python properties (see link in datastore_get_lazy), and because we do
    a bunch of work to convert to the correct type."""

    def __init__(self, entity_proto):
        self.__key = db.Key._FromPb(entity_proto.key())
        self.__properties = {}
        for prop_list in (entity_proto.property_list(), entity_proto.raw_property_list()):
            for prop in prop_list:
                # TODO: Entity._FromPb decodes names from UTF-8. However, Python identifiers can
                # only contain [A-za-z0-9_], so I don't think it is possible to access a property
                # with a special character: ignoring this for now
                name = prop.name()
                if prop.multiple():
                    current = self.__properties.setdefault(name, [])
                    current.append(prop)
                else:
                    # TODO: check for duplicates? should not happen
                    self.__properties[name] = prop

    def key(self):
        return self.__key

    def __getattr__(self, prop_name):
        prop = self.__properties.get(prop_name)
        if not prop:
            raise AttributeError("entity for kind '%s' has no attribute '%s'" % (
                self.__key.kind(), prop_name))

        if isinstance(prop, list):
            converted = [datastore_types.FromPropertyPb(p) for p in prop]
        else:
            converted = datastore_types.FromPropertyPb(prop)

        # store on this object: don't call __getattr__ again
        setattr(self, prop_name, converted)
        return converted

    @staticmethod
    def deserialize(protobuf_bytes):
        proto = entity_pb.EntityProto(protobuf_bytes)
        return LazyEntity(proto)
