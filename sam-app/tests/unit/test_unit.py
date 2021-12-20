import unittest
from unittest.mock import patch, Mock, MagicMock, PropertyMock
from document_search import app


class SearchUnitTests(unittest.TestCase):
    def test_simple_case(self):
        # arrange AAA

        # act
        results = app.lambda_handler({}, "")

        # assert
        self.assertGreater(len(results), 0)


if __name__ == "__main__":

    unittest.main()