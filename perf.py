import time
import logging

from google.appengine.api import datastore
from google.appengine.datastore import entity_pb
from google.appengine.ext import db
from google.appengine.ext import ndb
import webapp2

import datastore_lazy
import modelgen
import models_generated

# Produces lots of output but lets you view what the entities actually look like
DUMP_ENTITIES = False

def output(response, message):
    response.write(message + '\n')
    logging.info(message)

def ndb_get_multi_nocache(keys):
    # disable NDB's caching since it bypasses all deserialization,
    # which is what we want to measure
    return ndb.get_multi(keys, use_cache=False, use_memcache=False)

ITERATIONS = 10
def bench(response, model_class, keys):
    if issubclass(model_class, db.Model):
        get_func = db.get
    else:
        get_func = ndb_get_multi_nocache

    for i in xrange(ITERATIONS):
        total = 0
        start = time.time()
        entities = get_func(keys)
        end = time.time()
        output(response, '  %s.get %d entities in %f seconds (total: %d)' % (
            model_class.__name__, len(entities), (end-start), total))

    if issubclass(model_class, ndb.Model):
        keys = [k.to_old_key() for k in keys]

    for i in xrange(ITERATIONS):
        start = time.time()
        rpc = datastore.GetAsync(keys)
        entities = rpc.get_result()
        end = time.time()

        if DUMP_ENTITIES and i == 0:
            response.write('\n')
            response.write('## ENTITY CONTENTS:\n')
            response.write(repr(entities))
            response.write('\n\n')

            for i, entity in enumerate(entities):
                response.write('  %d: %d keys %d serialized bytes\n' % (i, len(entity), entity.ToPb().ByteSize()))

        output(response, '  datastore.GetAsync %d entities in %f seconds (total %d)' % (
            len(entities), (end-start), total))

    for i in xrange(ITERATIONS):
        start = time.time()
        entities = datastore_lazy.get(keys)
        end = time.time()

        output(response, '  datastore_lazy.get %d entities in %f seconds (total %d)' % (
            len(entities), (end-start), total))

DB_MODEL_CLASSES = [
    models_generated.Model10,
    models_generated.Model100,
    models_generated.Expando100,
]
NDB_MODEL_CLASSES = [
    models_generated.NdbModel100,
    models_generated.NdbExpando100,
]
MODEL_CLASSES = DB_MODEL_CLASSES + NDB_MODEL_CLASSES

INSTANCES_TO_CREATE = 100
class DbEntitySetup(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain;charset=UTF-8'

        instances = []
        ndb_instances = []
        for _ in xrange(INSTANCES_TO_CREATE):
            for model_class in MODEL_CLASSES:
                instance = modelgen.instance(model_class)
                if isinstance(instance, db.Model):
                    instances.append(instance)
                else:
                    ndb_instances.append(instance)
        db.put(instances)
        ndb.put_multi(ndb_instances)
        self.response.write('Put %d entities to the datastore' % (
            len(instances) + len(ndb_instances)))


NUM_INSTANCES_TO_DESERIALIZE = 20


def find_keys(model_class, limit):
    if issubclass(model_class, db.Model):
        keys = list(model_class.all(keys_only=True).run(
            limit=limit, batch_size=limit))
    else:
        keys = model_class.query().fetch(limit, keys_only=True)
    return keys


def find_keys_and_bench(response, model_class):
    # Query for models
    keys = find_keys(model_class, NUM_INSTANCES_TO_DESERIALIZE)

    response.write('## ENTITY KEYS:\n')
    for key in keys:
        if isinstance(key, db.Key):
            s = str(key)
        else:
            s = key.urlsafe()
        response.write(s + '\n')
    if len(keys) == 0:
        response.write("\n\n### ERROR NO ENTITIES ###")
        return

    bench(response, model_class, keys)



class PythonListHolder(object):
    def __init__(self):
        self._list = [1]

    def property_size(self):
        return len(self._list)


SERIALIZATION_ITERATIONS = 100
def benchmark_serialization(response, model_instance):
    # How data gets from a db.Model subclass to bytes:
    # 1. db.Model is converted to a datastore.Entity
    # 2. datastore.Entity is converted to a protocol buffer object: EntityProto
    # 3. EntityProto is serialized
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity = model_instance._populate_entity(datastore.Entity)
        entity_proto = entity.ToPb()
        serialized = entity_proto.SerializeToString()
    end = time.time()
    output(response, 'serialized from model %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity.ToPb()
        serialized = entity_proto.SerializeToString()
    end = time.time()
    output(response, 'serialized from datastore.Entity %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        serialized = entity_proto.SerializeToString()
    end = time.time()
    output(response, 'serialized from entity_pb.EntityProto %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        entity = datastore.Entity.FromPb(entity_proto)
        # from model_from_protobuf
        deserialized = db.class_for_kind(entity.kind()).from_entity(entity)
    end = time.time()
    output(response, 'deserialized to model %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        entity = datastore.Entity.FromPb(entity_proto)
    end = time.time()
    output(response, 'deserialized to datastore.Entity %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
    end = time.time()
    output(response, 'deserialized to entity_pb.EntityProto %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto.Clear()
        entity_proto.MergeFromString(serialized)
    end = time.time()
    output(response, 'deserialized to entity_pb.EntityProto with reuse %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))
    output(response, '  (entity has %d keys)' % len(entity))

    # model / LazyEntity property access tests
    response.write('\n### model / LazyEntity property access times\n')
    total_length = 0
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        entity = datastore.Entity.FromPb(entity_proto)
        # from model_from_protobuf
        deserialized = db.class_for_kind(entity.kind()).from_entity(entity)
        total_length += len(deserialized.prop_a)
    end = time.time()
    output(response, 'model deserialized and accessed one property %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    total_length = 0
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        entity = datastore.Entity.FromPb(entity_proto)
        # from model_from_protobuf
        deserialized = db.class_for_kind(entity.kind()).from_entity(entity)
        total_length += len(deserialized.prop_a)
        total_length += len(deserialized.prop_b)
        total_length += len(deserialized.prop_c)
        total_length += len(deserialized.prop_d)
        total_length += len(deserialized.prop_e)
    end = time.time()
    output(response, 'model deserialized and accessed five properties %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    total_length = 0
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        deserialized = datastore_lazy.LazyEntity(entity_proto)
        total_length += len(deserialized.prop_a)
    end = time.time()
    output(response, 'LazyEntity deserialized and accessed one property %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    total_length = 0
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        entity_proto = entity_pb.EntityProto(serialized)
        deserialized = datastore_lazy.LazyEntity(entity_proto)
        total_length += len(deserialized.prop_a)
        total_length += len(deserialized.prop_b)
        total_length += len(deserialized.prop_c)
        total_length += len(deserialized.prop_d)
        total_length += len(deserialized.prop_e)
    end = time.time()
    output(response, 'LazyEntity deserialized and accessed five properties %d times in %f s' % (SERIALIZATION_ITERATIONS, end-start))

    response.write('\n### protocol buffer / pure python access times\n')
    total = 0
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        total += entity_proto.property_size()
    end = time.time()
    output(response, 'protocol buffer entity_proto.property_size access in %f s' % (end-start))

    total = 0
    obj = PythonListHolder()
    start = time.time()
    for _ in xrange(SERIALIZATION_ITERATIONS):
        total += obj.property_size()
    end = time.time()
    output(response, 'PythonListHolder.property_size access in %f s' % (end-start))

    # output(response, '\n')
    # output(response, 'path: ' + repr(model_instance.key().to_path()))
    # output(response, str(entity_proto))
    # output(response, '\n')


class DbEntityTest(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain;charset=UTF-8'

        for model_class in MODEL_CLASSES:
            self.response.write('\n\n## %s:\n' % (model_class.__name__))
            find_keys_and_bench(self.response, model_class)


class SerializationTest(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain;charset=UTF-8'

        for model_class in DB_MODEL_CLASSES:
            q = db.Query(model_class)
            instance = q.get()
            self.response.write('\n\n## %s:\n' % (model_class.__name__))
            benchmark_serialization(self.response, instance)


app = webapp2.WSGIApplication([
    ('/db_entity_setup', DbEntitySetup),
    ('/db_entity_test', DbEntityTest),
    ('/serialization_test', SerializationTest),
])
