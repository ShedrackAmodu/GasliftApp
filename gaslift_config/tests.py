from django.test import RequestFactory, SimpleTestCase, override_settings

from gaslift_config.views import download_manual_pdf


class ManualPdfViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'])
    def test_download_manual_pdf_returns_pdf_response_without_messages_middleware(self):
        request = self.factory.get('/user-manual/', HTTP_HOST='localhost')
        request.user = None

        response = download_manual_pdf(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Gas_Lift_User_Manual.pdf', response['Content-Disposition'])
        self.assertGreater(len(response.content), 0)

    @override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'])
    def test_download_manual_pdf_can_render_inline_in_browser(self):
        request = self.factory.get('/user-manual/?inline=1', HTTP_HOST='localhost')
        request.user = None

        response = download_manual_pdf(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('inline; filename="Gas_Lift_User_Manual.pdf"', response['Content-Disposition'])
