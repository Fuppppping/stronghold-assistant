import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from stronghold.pc_input import ShopButton, identify_shop_button, operate_shop
from stronghold.vision import Line
from stronghold.windows import Window


class ShopButtonTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGB", (2560, 1440), "#234565")
        self.recognizer = Mock()
        self.preparation = [Line("回合", (400, 10, 460, 30), .99),
                            Line("休息一下", (510, 10, 620, 30), .99)]
        self.button = Line("收起", (1160, 650, 1210, 670), .99)

    def test_uses_raw_client_coordinates(self):
        self.recognizer.ocr.side_effect = [self.preparation, [self.button]]
        result = identify_shop_button(self.recognizer, self.image)
        self.assertEqual(result.label, "收起")
        self.assertEqual(result.point, (2370, 1320))

    def test_rejects_a_button_outside_preparation(self):
        self.recognizer.ocr.return_value = [self.button]
        with self.assertRaisesRegex(RuntimeError, "整备界面"):
            identify_shop_button(self.recognizer, self.image)

    def test_rejects_multiple_candidate_buttons(self):
        self.recognizer.ocr.side_effect = [self.preparation, [self.button, self.button]]
        with self.assertRaisesRegex(RuntimeError, "唯一识别"):
            identify_shop_button(self.recognizer, self.image)


class ShopOperationTests(unittest.TestCase):
    def setUp(self):
        game = Window(5, "明日方舟", "Arknights.exe", 100)
        image = Image.new("RGB", (1280, 720), "#234565")
        rect = (0, 0, 1280, 720)
        mocks = {
            "is_admin": True, "list_windows": [game], "foreground": game.hwnd,
            "capture_bounds": rect, "capture": image,
        }
        for name, value in mocks.items():
            self.enterContext(patch(f"stronghold.pc_input.windows.{name}", return_value=value))
        self.enterContext(patch("maa.toolkit.Toolkit.init_option"))
        self.enterContext(patch("stronghold.pc_input.sleep"))
        controller_type = self.enterContext(patch("maa.controller.Win32Controller"))
        self.controller = controller_type.return_value
        self.controller.resolution = image.size
        self.button = self.enterContext(patch("stronghold.pc_input.identify_shop_button"))
        self.log_directory = Path(self.enterContext(TemporaryDirectory()))

    def test_open_only_sends_one_click_and_checks_result(self):
        self.button.side_effect = [ShopButton("展开", (1180, 655)), ShopButton("收起", (1180, 655))]
        self.assertEqual(operate_shop(5, "open", Mock(), self.log_directory), "调度中心已展开")
        self.controller.post_touch_down.assert_called_once_with(1180, 655)
        self.controller.post_touch_up.assert_called_once_with()
        self.controller.post_inactive.assert_called_once_with()

    def test_open_when_already_open_sends_no_input(self):
        self.button.return_value = ShopButton("收起", (1180, 655))
        self.assertEqual(operate_shop(5, "open", Mock(), self.log_directory), "调度中心已经展开")
        self.controller.post_touch_down.assert_not_called()
        self.controller.post_inactive.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
