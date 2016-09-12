#!/usr/bin/python

import random

from google.appengine.ext import db

DB_IMPORT = "from google.appengine.ext import db"

LETTERS_START = ord('a')
LETTERS_END = ord('z') + 1
BASE = LETTERS_END - LETTERS_START
LETTERS = ""
for i in xrange(LETTERS_START, LETTERS_END):
    LETTERS += chr(i)
assert len(LETTERS) == BASE

def base26(i):
    out = ""
    while True:
        char = LETTERS[i % BASE]
        out += char
        i = i / BASE
        if i == 0:
            break
    return out

def code(num_properties):
    out = []
    out.append('class Model%d(db.Model):' % num_properties)

    for i in xrange(num_properties):
        name = 'prop_' + base26(i)
        out.append('    %s = db.StringProperty(indexed=False)' % name)

    return '\n'.join(out) + '\n'


STRING_LENGTH = 20
def random_string():
    out = ""
    for i in xrange(STRING_LENGTH):
        out += random.choice(LETTERS)
    return out


def instance(model_class):
    inst = model_class()

    if isinstance(inst, db.Model):
        property_dict = model_class.properties()
    else:
        property_dict = model_class._properties

    for name, property_metadata in property_dict.iteritems():
        # assuming everything is a string
        setattr(inst, name, random_string())
    return inst


if __name__ == "__main__":
    print DB_IMPORT
    print
    print code(10)
    print
    print code(100)
