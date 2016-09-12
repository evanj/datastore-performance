# Datastore serialization performance test

Google App Engine's Python datastore library has very slow deserialization for models that have many properties. This project benchmarks this library.


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

Go to: https://[YOUR PROJECT ID].appspot.com/db_entity_test


## Results and notes

On an App Engine F1 instance:

   db.Model  10 properties: get: 79 ms  datastore.GetAsync: 60 ms
   db.Model 100 properties: get: 303 ms  datastore.GetAsync: 268 ms
 db.Expando 100 properties: get: 576 ms  datastore.GetAsync: 251 ms
  ndb.Model 100 properties: get: 154 ms  datastore.GetAsync: 208 ms
ndb.Expando 100 properties: get: 149 ms  datastore.GetAsync: 191 ms

Conclusions:
* db deserialization is slower than ndb. The times for datastore.GetAsync are basically constant since the data sizes are extremely similar. However, even the ndb.Model is faster than the db.Model.
* For db, using a db.Expando makes deserialization twice as slow. For ndb, there is no measurable difference.
* ndb get_multi is faster than datastore.GetAsync, so its likely the "entity" conversion that is slow (see below).

Notes:
* The first request to a new deploy seems to run faster than subsequent requests. My guess: Google removes the performance limits for this request to compensate for the overhead of loading code etc.
* With ndb's built-in caching turned on, the numbers are substantially faster.
* Even ignoring ndb's memcache, it seems to have much faster deserialization.


## How data gets from a db.Model to bytes

I walked through the code for the db library, and sending bytes to the datastore takes the following path, starting with a db.Model instance:

1. The db.Model is converted to a datastore.Entity (`instance._populate_entity(datastore.Entity)`)
2. The datastore.Entity is converted to an EntityProto protocol buffer object (`entity.ToPb()`)
3. The EntityProto is serialized to bytes: (`entity_proto.SerializeToString()`)


## How data gets from an ndb.Model to bytes

The ndb code is more convoluted than the db code, but I think it takes the following steps:

1. The ndb.Model is converted to an EntityProto by calling `entity._to_pb()`
2. The EntityProto is serialized to bytes by calling `entity_proto.SerializeToString()`
