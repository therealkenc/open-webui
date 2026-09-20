import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from open_webui.routers.openai import convert_to_responses_payload
from open_webui.utils import middleware


IMAGE = 'data:image/png;base64,aW1hZ2U='
FILE_URL = '/api/v1/files/screenshot-file/content'


def request_for(models=None, **state):
    return SimpleNamespace(
        state=SimpleNamespace(**state),
        app=SimpleNamespace(state=SimpleNamespace(OPENAI_MODELS=models or {})),
    )


def saved_screenshot_turn():
    return {
        'id': 'assistant-message',
        'role': 'assistant',
        'content': 'The page is ready.',
        'output': [
            {
                'type': 'function_call',
                'call_id': 'screenshot-call',
                'name': 'browser_take_screenshot',
                'arguments': '{}',
                'status': 'completed',
            },
            {
                'type': 'function_call_output',
                'call_id': 'screenshot-call',
                'output': [
                    {'type': 'input_text', 'text': 'Before:'},
                    {'type': 'input_image', 'image_url': FILE_URL, 'detail': 'high'},
                    {'type': 'input_text', 'text': 'After:'},
                    {'type': 'input_image', 'image_url': IMAGE},
                    {'type': 'input_text', 'text': 'Compare the status.'},
                ],
                'files': [{'type': 'image', 'url': FILE_URL}],
            },
            {
                'type': 'message',
                'role': 'assistant',
                'content': [{'type': 'output_text', 'text': 'The page is ready.'}],
            },
        ],
    }


class ModelProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_preset_resolves_base_model_connection(self):
        request = request_for({'qwen': {'id': 'qwen', 'urlIdx': 1}})
        model = {'id': 'visual-qwen', 'info': {'base_model_id': 'qwen'}}
        config = {
            'openai.api_base_urls': ['https://chat.example/v1', 'http://qwen/v1'],
            'openai.api_configs': {'0': {'api_type': 'chat_completions'}, '1': {'api_type': 'responses'}},
        }
        with patch.object(middleware.Config, 'get_many', AsyncMock(return_value=config)) as get_config:
            self.assertTrue(await middleware.model_uses_responses_api(request, model))
        get_config.assert_awaited_once_with('openai.api_base_urls', 'openai.api_configs')

    async def test_request_base_model_takes_precedence(self):
        request = request_for({'actual': {'urlIdx': '0'}, 'preset-default': {'urlIdx': 1}})
        request.base_model_id = 'actual'
        model = {'id': 'preset', 'info': {'base_model_id': 'preset-default'}}
        config = {
            'openai.api_base_urls': ['http://actual/v1', 'http://default/v1'],
            'openai.api_configs': {'0': {'api_type': 'responses'}, '1': {'api_type': 'chat_completions'}},
        }
        with patch.object(middleware.Config, 'get_many', AsyncMock(return_value=config)):
            self.assertTrue(await middleware.model_uses_responses_api(request, model))

    async def test_legacy_url_keyed_config_is_resolved(self):
        config = {
            'openai.api_base_urls': ['http://qwen/v1'],
            'openai.api_configs': {'http://qwen/v1': {'api_type': 'responses'}},
        }
        with patch.object(middleware.Config, 'get_many', AsyncMock(return_value=config)):
            self.assertTrue(await middleware.model_uses_responses_api(request_for(), {'id': 'qwen', 'urlIdx': 0}))

    async def test_index_config_takes_precedence_over_url_config(self):
        config = {
            'openai.api_base_urls': ['http://qwen/v1'],
            'openai.api_configs': {
                '0': {'api_type': 'chat_completions'},
                'http://qwen/v1': {'api_type': 'responses'},
            },
        }
        with patch.object(middleware.Config, 'get_many', AsyncMock(return_value=config)):
            self.assertFalse(await middleware.model_uses_responses_api(request_for(), {'id': 'qwen', 'urlIdx': 0}))

    async def test_unconfigured_connection_defaults_to_chat_completions(self):
        for config in ({}, {'openai.api_base_urls': [], 'openai.api_configs': {}}):
            with self.subTest(config=config):
                with patch.object(middleware.Config, 'get_many', AsyncMock(return_value=config)):
                    self.assertFalse(
                        await middleware.model_uses_responses_api(request_for(), {'id': 'qwen', 'urlIdx': 0})
                    )

    async def test_direct_ollama_pipe_and_unknown_models_skip_openai_lookup(self):
        cases = [
            (request_for(direct=True), {'id': 'qwen', 'urlIdx': 0}),
            (request_for(), {'id': 'qwen', 'owned_by': 'ollama', 'urlIdx': 0}),
            (request_for(), {'id': 'pipeline', 'pipe': {'type': 'pipe'}, 'urlIdx': 0}),
            (request_for(), {'id': 'unknown'}),
        ]
        for request, model in cases:
            with self.subTest(model=model, direct=getattr(request.state, 'direct', False)):
                with patch.object(middleware.Config, 'get_many', AsyncMock()) as get_config:
                    self.assertFalse(await middleware.model_uses_responses_api(request, model))
                    get_config.assert_not_awaited()


class ToolImageProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_replay_resolves_images_inside_tool_output_in_order(self):
        saved = saved_screenshot_turn()
        messages = [
            {'role': 'user', 'content': 'Inspect the page.'},
            saved,
            {'role': 'user', 'content': 'What changed?'},
        ]
        original = copy.deepcopy(messages)
        user = SimpleNamespace(id='owner')
        form = {
            'model': 'qwen',
            'messages': middleware.process_messages_with_output(messages, flatten_tool_images=False),
        }

        with patch.object(middleware, 'get_image_base64_from_url', AsyncMock(return_value=IMAGE)) as get_image:
            await middleware.convert_url_images_to_base64(form, user=user)
        payload = convert_to_responses_payload(form)

        self.assertEqual(
            [item['type'] for item in payload['input']],
            ['message', 'function_call', 'function_call_output', 'message', 'message'],
        )
        call, result = payload['input'][1:3]
        self.assertEqual(call['call_id'], 'screenshot-call')
        self.assertEqual(result['call_id'], call['call_id'])
        self.assertEqual(
            result['output'],
            [
                {'type': 'input_text', 'text': 'Before:'},
                {'type': 'input_image', 'image_url': IMAGE, 'detail': 'high'},
                {'type': 'input_text', 'text': 'After:'},
                {'type': 'input_image', 'image_url': IMAGE},
                {'type': 'input_text', 'text': 'Compare the status.'},
            ],
        )
        get_image.assert_awaited_once_with('screenshot-file', user=user)
        self.assertEqual(
            messages, original, 'Request conversion must not replace persisted file references with base64'
        )

    async def test_chat_completions_replay_injects_images_in_user_message(self):
        saved = saved_screenshot_turn()
        original = copy.deepcopy(saved)
        messages = middleware.process_messages_with_output([saved], flatten_tool_images=True)

        self.assertEqual([message['role'] for message in messages], ['assistant', 'tool', 'user', 'assistant'])
        self.assertEqual(messages[1]['tool_call_id'], 'screenshot-call')
        self.assertEqual(messages[1]['content'], 'Before:After:Compare the status.')
        self.assertEqual(
            [part['image_url']['url'] for part in messages[2]['content'] if part['type'] == 'image_url'],
            [FILE_URL, IMAGE],
        )
        with patch.object(middleware, 'get_image_base64_from_url', AsyncMock(return_value=IMAGE)):
            await middleware.convert_url_images_to_base64({'messages': messages}, user=SimpleNamespace(id='owner'))
        self.assertEqual(messages[2]['content'][1]['image_url']['url'], IMAGE)
        self.assertEqual(saved, original)

    async def test_chat_image_url_preserves_detail_and_forwards_user(self):
        user = SimpleNamespace(id='owner')
        form = {
            'messages': [
                {'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': FILE_URL, 'detail': 'high'}}]}
            ]
        }
        with patch.object(middleware, 'get_image_base64_from_url', AsyncMock(return_value=IMAGE)) as get_image:
            result = await middleware.convert_url_images_to_base64(form, user=user)
        self.assertEqual(
            result['messages'][0]['content'], [{'type': 'image_url', 'image_url': {'url': IMAGE, 'detail': 'high'}}]
        )
        get_image.assert_awaited_once_with('screenshot-file', user=user)

    async def test_inline_images_and_other_content_are_unchanged(self):
        form = {
            'messages': [
                {'role': 'user', 'content': 'A plain message'},
                {
                    'role': 'tool',
                    'content': [
                        {'type': 'input_text', 'text': 'Screenshot'},
                        {'type': 'input_image', 'image_url': IMAGE, 'detail': 'high'},
                        {'type': 'image_url', 'image_url': {'url': IMAGE, 'detail': 'low'}},
                        {'type': 'image_url', 'image_url': IMAGE},
                        {'type': 'input_file', 'file_id': 'document'},
                    ],
                },
            ]
        }
        original = copy.deepcopy(form)
        with patch.object(middleware, 'get_image_base64_from_url', AsyncMock()) as get_image:
            await middleware.convert_url_images_to_base64(form, user=SimpleNamespace(id='owner'))
        self.assertEqual(form, original)
        get_image.assert_not_awaited()

    async def test_missing_or_denied_tool_images_become_text_placeholders(self):
        user = SimpleNamespace(id='other-user')
        for image_type, image_url, text_type in (
            ('input_image', FILE_URL, 'input_text'),
            ('image_url', {'url': FILE_URL}, 'text'),
        ):
            with self.subTest(image_type=image_type):
                form = {'messages': [{'role': 'tool', 'content': [{'type': image_type, 'image_url': image_url}]}]}
                for failure in (None, OSError('image storage unavailable')):
                    attempt = copy.deepcopy(form)
                    resolver = AsyncMock(return_value=None, side_effect=failure)
                    with patch.object(middleware, 'get_image_base64_from_url', resolver) as get_image:
                        await middleware.convert_url_images_to_base64(attempt, user=user)
                    self.assertEqual(
                        attempt['messages'][0]['content'],
                        [{'type': text_type, 'text': '[Tool image unavailable or access denied]'}],
                    )
                    get_image.assert_awaited_once_with('screenshot-file', user=user)


if __name__ == '__main__':
    unittest.main()
