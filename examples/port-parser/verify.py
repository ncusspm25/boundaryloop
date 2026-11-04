import inspect
import unittest

from parser import parse_port


class PortContract(unittest.TestCase):
    def test_public_api(self):
        self.assertEqual(list(inspect.signature(parse_port).parameters), ["value"])

    def test_valid(self):
        self.assertEqual(parse_port("443"), 443)
        self.assertEqual(parse_port(1), 1)
        self.assertEqual(parse_port(65535), 65535)

    def test_reject_bool(self):
        with self.assertRaises(ValueError):
            parse_port(True)

    def test_range(self):
        for value in (0, -1, 65536):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_port(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
