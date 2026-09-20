import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from open_webui.utils import middleware


class MCPToolImageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.request = SimpleNamespace()
        self.user = SimpleNamespace(id='test-user')
        self.metadata = {'chat_id': 'chat', 'message_id': 'message', 'session_id': 'session'}
        self.image_data = 'c2NyZWVuc2hvdA=='
        self.image_url = f'data:image/png;base64,{self.image_data}'
        self.file_url = '/api/v1/files/screenshot-file/content'
        self.upload = AsyncMock(return_value=self.file_url)
        patcher = patch.object(middleware, 'get_file_url_from_base64', self.upload)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def process(self, result, output_parts=None, metadata=None):
        return await middleware.process_tool_result(
            self.request,
            'browser_take_screenshot',
            result,
            'mcp',
            metadata=self.metadata if metadata is None else metadata,
            user=self.user,
            output_parts=output_parts,
        )

    async def test_native_mcp_image_is_saved_for_display_and_model(self):
        parts = []
        result = [{'type': 'image', 'mimeType': 'image/png', 'data': self.image_data}]

        processed = await self.process(result, parts)

        self.assertEqual(len(processed), 3)
        text, files, embeds = processed
        self.assertEqual(json.loads(text), {'results': []})
        self.assertEqual(files, [{'type': 'image', 'url': self.file_url}])
        self.assertEqual(embeds, [])
        self.assertEqual(parts, [{'type': 'input_image', 'image_url': self.file_url}])
        self.upload.assert_awaited_once_with(self.request, self.image_url, self.metadata, self.user)
        self.assertNotIn(self.image_data, json.dumps(processed))

    async def test_embedded_resource_image_uses_the_same_persisted_reference(self):
        parts = []
        result = [
            {
                'type': 'resource',
                'resource': {'uri': 'image://screenshot', 'mimeType': 'image/png', 'blob': self.image_data},
            }
        ]

        _, files, _ = await self.process(result, parts)

        self.assertEqual(files, [{'type': 'image', 'url': self.file_url}])
        self.assertEqual(parts, [{'type': 'input_image', 'image_url': self.file_url}])
        self.upload.assert_awaited_once_with(self.request, self.image_url, self.metadata, self.user)

    async def test_mixed_mcp_content_preserves_order_and_does_not_mutate_input(self):
        second_file = '/api/v1/files/second-screenshot/content'
        self.upload.side_effect = [self.file_url, second_file]
        result = [
            {'type': 'text', 'text': 'Before clicking'},
            {'type': 'image', 'mimeType': 'image/png', 'data': self.image_data},
            {'type': 'resource', 'resource': {'uri': 'text://status', 'text': '{"clicked": true}'}},
            {
                'type': 'resource',
                'resource': {'uri': 'image://after', 'mimeType': 'image/png', 'blob': 'YWZ0ZXI='},
            },
            {'type': 'text', 'text': 'After clicking'},
        ]
        original = copy.deepcopy(result)
        parts = []

        _, files, _ = await self.process(result, parts)

        self.assertEqual(
            parts,
            [
                {'type': 'input_text', 'text': 'Before clicking'},
                {'type': 'input_image', 'image_url': self.file_url},
                {'type': 'input_text', 'text': '{"clicked": true}'},
                {'type': 'input_image', 'image_url': second_file},
                {'type': 'input_text', 'text': 'After clicking'},
            ],
        )
        self.assertEqual([file['url'] for file in files], [self.file_url, second_file])
        self.assertEqual(result, original)
        self.assertEqual(self.upload.await_count, 2)

    async def test_image_metadata_excludes_the_original_binary_payload(self):
        metadata = {**self.metadata, 'result': {'data': self.image_data}, 'unrelated': 'value'}

        await self.process([{'type': 'image', 'data': self.image_data}], metadata=metadata)

        self.assertEqual(self.upload.await_args.args[2], self.metadata)

    async def test_image_supports_absent_metadata(self):
        parts = []

        processed = await middleware.process_tool_result(
            self.request,
            'browser_take_screenshot',
            [{'type': 'image', 'data': self.image_data}],
            'mcp',
            metadata=None,
            user=self.user,
            output_parts=parts,
        )

        self.assertEqual(processed[1], [{'type': 'image', 'url': self.file_url}])
        self.upload.assert_awaited_once_with(
            self.request,
            self.image_url,
            {'chat_id': None, 'message_id': None, 'session_id': None},
            self.user,
        )

    async def test_text_and_audio_keep_legacy_text_and_attachment_behavior(self):
        audio = {'type': 'audio', 'mimeType': 'audio/wav', 'data': 'YXVkaW8='}
        self.upload.return_value = '/api/v1/files/audio-file/content'
        parts = []

        processed = await self.process([{'type': 'text', 'text': 'Audio description'}, audio], parts)

        self.assertEqual(
            processed,
            ('Audio description', [{'type': 'audio', 'url': '/api/v1/files/audio-file/content'}], []),
        )
        self.assertEqual(parts, [])
        self.upload.assert_awaited_once_with(
            self.request,
            'data:audio/wav;base64,YXVkaW8=',
            {**self.metadata, 'result': audio},
            self.user,
        )

    async def test_build_keeps_images_visible_without_uploading_them_again(self):
        collected = []
        text, files, _ = await self.process(
            [{'type': 'text', 'text': 'Screenshot'}, {'type': 'image', 'data': self.image_data}], collected
        )
        result = {'content': text, 'files': files, 'output_parts': collected}
        original = copy.deepcopy(result)

        parts, displayed_files = await middleware.build_tool_result_output(
            self.request, result, self.metadata, self.user
        )

        self.assertEqual(parts, collected)
        self.assertEqual(displayed_files, files)
        self.assertEqual(result, original)
        self.upload.assert_awaited_once()

    async def test_build_saves_inline_image_once_and_updates_its_existing_part(self):
        result = {
            'content': 'Screenshot',
            'output_parts': [
                {'type': 'input_text', 'text': 'Screenshot'},
                {'type': 'input_image', 'image_url': self.image_url},
            ],
            'files': [{'type': 'image', 'url': self.image_url}, {'type': 'audio', 'url': '/audio.wav'}],
        }
        original = copy.deepcopy(result)

        parts, files = await middleware.build_tool_result_output(self.request, result, self.metadata, self.user)

        self.assertEqual(
            parts,
            [
                {'type': 'input_text', 'text': 'Screenshot'},
                {'type': 'input_image', 'image_url': self.file_url},
            ],
        )
        self.assertEqual(files, [{'type': 'image', 'url': self.file_url}, {'type': 'audio', 'url': '/audio.wav'}])
        self.assertEqual(result, original)
        self.upload.assert_awaited_once()

    async def test_build_promotes_legacy_image_attachment_into_model_content(self):
        result = {'content': 'Screenshot', 'files': [{'type': 'image', 'url': self.file_url}]}

        parts, files = await middleware.build_tool_result_output(self.request, result, self.metadata, self.user)

        self.assertEqual(
            parts,
            [
                {'type': 'input_text', 'text': 'Screenshot'},
                {'type': 'input_image', 'image_url': self.file_url},
            ],
        )
        self.assertEqual(files, result['files'])
        self.upload.assert_not_awaited()

    async def test_storage_failure_retains_image_data_for_model_and_display(self):
        self.upload.side_effect = OSError('Storage unavailable')
        parts = []

        with self.assertLogs(middleware.log, level='WARNING'):
            _, files, _ = await self.process([{'type': 'image', 'data': self.image_data}], parts)

        self.assertEqual(parts, [{'type': 'input_image', 'image_url': self.image_url}])
        self.assertEqual(files, [{'type': 'image', 'url': self.image_url}])

    async def test_empty_storage_result_retains_inline_image(self):
        self.upload.return_value = None

        url = await middleware.store_tool_image(self.request, self.image_url, self.metadata, self.user)

        self.assertEqual(url, self.image_url)


if __name__ == '__main__':
    unittest.main()
