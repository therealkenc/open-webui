import copy
import unittest

from open_webui.utils.misc import convert_output_to_messages


def tool_output(call_id, parts):
    return [
        {
            'type': 'function_call',
            'call_id': call_id,
            'name': 'browser_take_screenshot',
            'arguments': '{}',
            'status': 'completed',
        },
        {'type': 'function_call_output', 'call_id': call_id, 'output': parts},
    ]


class ToolOutputConversionTests(unittest.TestCase):
    def test_responses_preserves_interleaved_tool_output(self):
        parts = [
            {'type': 'input_text', 'text': 'Before clicking:'},
            {'type': 'input_image', 'image_url': 'data:image/png;base64,YmVmb3Jl', 'detail': 'high'},
            {'type': 'input_text', 'text': 'After clicking:'},
            {'type': 'input_image', 'image_url': 'data:image/png;base64,YWZ0ZXI='},
            {'type': 'input_text', 'text': 'Compare these screenshots.'},
        ]
        output = tool_output('screenshots', parts)
        original = copy.deepcopy(output)

        messages = convert_output_to_messages(output, raw=True)

        self.assertEqual([message['role'] for message in messages], ['assistant', 'tool'])
        self.assertEqual(messages[1]['tool_call_id'], 'screenshots')
        self.assertEqual(messages[1]['content'], parts)
        self.assertEqual(output, original)

    def test_responses_keeps_image_only_output_without_synthetic_text(self):
        parts = [{'type': 'input_image', 'image_url': 'data:image/png;base64,aW1hZ2U='}]

        messages = convert_output_to_messages(tool_output('image-only', parts))

        self.assertEqual(messages[1]['content'], parts)

    def test_responses_keeps_persisted_image_url_for_later_resolution(self):
        parts = [
            {'type': 'input_text', 'text': 'Screenshot:'},
            {'type': 'input_image', 'image_url': '/api/v1/files/screenshot-file/content'},
            {'type': 'input_text', 'text': 'Read the status.'},
        ]

        messages = convert_output_to_messages(tool_output('persisted-image', parts), raw=True)

        self.assertEqual(messages[1]['content'], parts)

    def test_text_only_tool_output_stays_a_string(self):
        parts = [
            {'type': 'input_text', 'text': 'Count: '},
            {'type': 'input_text', 'text': 3},
            {'type': 'input_image', 'image_url': ''},
        ]

        for flatten in (False, True):
            with self.subTest(flatten_tool_images=flatten):
                messages = convert_output_to_messages(tool_output('text-only', parts), flatten_tool_images=flatten)
                self.assertEqual([message['role'] for message in messages], ['assistant', 'tool'])
                self.assertEqual(messages[1]['content'], 'Count: 3')

    def test_chat_completions_flattens_images_after_all_tool_outputs(self):
        first_image = 'data:image/png;base64,YmVmb3Jl'
        second_image = 'data:image/png;base64,YWZ0ZXI='
        output = [
            *tool_output(
                'before',
                [
                    {'type': 'input_text', 'text': 'Before '},
                    {'type': 'input_image', 'image_url': first_image},
                    {'type': 'input_text', 'text': 'clicking'},
                ],
            ),
            *tool_output(
                'after',
                [
                    {'type': 'input_text', 'text': 'After clicking'},
                    {'type': 'input_image', 'image_url': second_image},
                ],
            ),
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'The page changed.'}]},
        ]

        messages = convert_output_to_messages(output, raw=True, flatten_tool_images=True)

        self.assertEqual([message['role'] for message in messages], ['assistant', 'tool', 'tool', 'user', 'assistant'])
        self.assertEqual(
            [(message['tool_call_id'], message['content']) for message in messages if message['role'] == 'tool'],
            [('before', 'Before clicking'), ('after', 'After clicking')],
        )
        self.assertEqual(
            messages[3]['content'][1:],
            [
                {'type': 'image_url', 'image_url': {'url': first_image}},
                {'type': 'image_url', 'image_url': {'url': second_image}},
            ],
        )


if __name__ == '__main__':
    unittest.main()
