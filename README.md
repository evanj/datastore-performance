# Datastore serialization performance test

Google App Engine's Python original datastore library called "db" has very slow deserialization for models that have many properties. This project benchmarks this library, and compares it to ndb and our own hacked up minimal version.


## Setup

1. Install the `gcloud` tool: https://cloud.google.com/sdk/gcloud/ ; Install 
2. Run `./setup_venv.py` to set up a Python virtualenv with the correct dependencies.
3. Create a new App Engine project


## Run Tests

1. Run `./venv/bin/python -m unittest discover` to run all tests


## Deploy

1. Run `gcloud app deploy performance.yaml --project=[YOUR PROJECT ID]`


## Test data generation

Create a set of instances that get used for the test. This needs to be done only once:

https://[YOUR PROJECT ID].appspot.com/db_entity_setup


## Run the performance test

Go to the following URLs

* https://[YOUR PROJECT ID].appspot.com/db_entity_test
* https://[YOUR PROJECT ID].appspot.com/serialization_test


## Results and notes

On an App Engine F1 instance, the average time to get 20 entities was the following. Don't trust these numbers too much: I did not repeat them substantially, 

Model class | Num. Properties | (db|ndb).get | datastore.GetAsync | lazy.get
---         | ---             | ---          | ---                | ---
   db.Model | 10 properties   |  79 ms       | 60 ms              | 32 ms
   db.Model | 100 properties  | 303 ms       | 268 ms             | 80 ms
 db.Expando | 100 properties  | 576 ms       | 251 ms             | 80 ms
  ndb.Model | 100 properties  | 154 ms       | 208 ms             | 70 ms
ndb.Expando | 100 properties  | 149 ms       | 191 ms             | 59 ms


Conclusions:
* db deserialization is slower than ndb. The times for datastore.GetAsync are basically constant since the data sizes are extremely similar. However, even the ndb.Model is faster than the db.Model.
* For db, using a db.Expando makes deserialization twice as slow. For ndb, there is no measurable difference.
* ndb get_multi is faster than datastore.GetAsync, so its likely the "entity" conversion that is slow (see below).

Notes:
* The first request to a new deploy seems to run faster than subsequent requests. My guess: Google removes the performance limits for this request to compensate for the overhead of loading code etc.
* With ndb's built-in caching turned on, the numbers are substantially faster.
* Even ignoring ndb's memcache, it seems to have faster deserialization.
* There is nearly zero performance difference for these different requests when using dev_appserver.py, although the larger objects are slower.

* The python-compat "flexible environment" runtime is significantly slower at serializing/deserializing to the protocol buffer objects than the standard environment. Accessing protocol buffer attributes is slower than accessing native Python attributes in the standard environment, but the same speed in the flexible environment. The standard environment probably uses native code, while the flexible environment uses a Python implementation. This means that calling App Engine APIs is relatively more expensive in the flexible environment.


## How data gets from a db.Model to bytes

I walked through the code for the db library, and sending bytes to the datastore takes the following path, starting with a db.Model instance:

1. The db.Model is converted to a datastore.Entity (`instance._populate_entity(datastore.Entity)`)
2. The datastore.Entity is converted to an EntityProto protocol buffer object (`entity.ToPb()`)
3. The EntityProto is serialized to bytes: (`entity_proto.SerializeToString()`)


## How data gets from an ndb.Model to bytes

The ndb code is more convoluted than the db code, but I think it takes the following steps:

1. The ndb.Model is converted to an EntityProto by calling `entity._to_pb()`
2. The EntityProto is serialized to bytes by calling `entity_proto.SerializeToString()`
