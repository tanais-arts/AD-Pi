import unittest
from unittest.mock import patch, sentinel

from generate_sync import find_font


class FontRenderingTests(unittest.TestCase):
    def test_comic_sans_is_preferred_to_dejavu_on_linux(self):
        available = {
            '/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS_Bold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        }
        with patch('generate_sync.Path.exists', autospec=True,
                   side_effect=lambda path: str(path) in available), \
             patch('generate_sync.ImageFont.truetype', return_value=sentinel.font) as load:
            self.assertIs(find_font(48), sentinel.font)
        load.assert_called_once_with(
            '/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS_Bold.ttf', 48)

    def test_french_characters_are_not_missing_glyphs(self):
        font = find_font(48)
        missing = bytes(font.getmask('\U0010ffff'))
        for character in '\u00e0\u00e2\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u0153\u00c9\u20ac':
            with self.subTest(character=character):
                self.assertNotEqual(bytes(font.getmask(character)), missing)


if __name__ == '__main__':
    unittest.main()
