import os
import unittest
from unittest.mock import patch
from app.intelligence import analyze
from app.sentiment_model import predict, status


class ModelTests(unittest.TestCase):
    def test_neural_provider_records_provenance(self):
        prediction = {'sentiment':'positive','score':.9,'probabilities':{'positive':.95,'neutral':.04,'negative':.01},'model':'test-model'}
        with patch.dict(os.environ,{'SENTIMENT_PROVIDER':'onnx'}), patch('app.sentiment_model.predict',return_value=prediction):
            result=analyze('Ce service est vraiment excellent et je suis très content.')
        self.assertEqual(result['sentiment'],'positive')
        self.assertEqual(result['model'],'test-model')
        self.assertEqual(result['aspects'].get('support'),'unclassified')

    def test_unsupported_language_abstains_without_loading(self):
        with patch('app.sentiment_model.load_model') as loader:
            self.assertEqual(predict('text','ja')['sentiment'],'unclassified')
            loader.assert_not_called()

    def test_provider_is_explicit_and_no_download_in_request(self):
        with patch.dict(os.environ,{'SENTIMENT_PROVIDER':'baseline'}):
            self.assertEqual(status()['languages'],['en'])
        with patch.dict(os.environ,{'SENTIMENT_PROVIDER':'onnx'}):
            self.assertIn('ar',status()['languages'])
        with patch.dict(os.environ,{'SENTIMENT_PROVIDER':'typo'}):
            with self.assertRaises(ValueError):status()

    @unittest.skipUnless(os.environ.get('RUN_MODEL_TESTS')=='1','Enable RUN_MODEL_TESTS=1 after downloading the pinned model.')
    def test_live_multilingual_inference(self):
        cases=[('Ce produit est excellent, je suis vraiment très content.','fr','positive'),
               ('Le service est horrible et je suis très déçu.','fr','negative'),
               ('هذا المنتج رائع وأنا سعيد جدا بالخدمة','ar','positive'),
               ('هذا التطبيق سيئ جدا ولا يعمل بشكل صحيح','ar','negative'),
               ('Este producto es excelente y estoy muy contento.','es','positive'),
               ('Dieses Produkt ist schrecklich und funktioniert nicht.','de','negative'),
               ('The support team was wonderful and very helpful.','en','positive'),
               ('The application is broken and customer support is terrible.','en','negative')]
        for text,language,label in cases:
            with self.subTest(language=language,text=text):
                result=predict(text,language)
                self.assertEqual(result['sentiment'],label)
                self.assertAlmostEqual(sum(result['probabilities'].values()),1.0)


if __name__=='__main__':unittest.main()
