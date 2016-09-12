import unittest

from google.appengine.ext import db

import modelgen


class SomeModel(db.Model):
    foo = db.StringProperty(indexed=False)
    bar = db.StringProperty(indexed=False)


class Test(unittest.TestCase):
    def test_code(self):
        output = modelgen.code(10)

        self.assertIn('Model10', output)
        self.assertIn('prop_g', output)
        output = modelgen.DB_IMPORT + "\n" + output

        exec_globals = {}
        exec output in exec_globals

    def test_instance(self):
        instance = modelgen.instance(SomeModel)
        self.assertEquals(modelgen.STRING_LENGTH, len(instance.foo))
        self.assertEquals(modelgen.STRING_LENGTH, len(instance.bar))
        self.assertNotEquals(instance.foo, instance.bar)


if __name__ == "__main__":
    unittest.main()
