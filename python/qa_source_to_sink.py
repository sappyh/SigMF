import json
import uuid
import tempfile
import os
import shutil
from gnuradio import gr_unittest, gr, analog, blocks
from sigmf import sigmf_swig as sigmf
from test_blocks import (advanced_tag_injector, sample_counter,
                         sample_producer, msg_sender, tag_collector)


class qa_source_to_sink(gr_unittest.TestCase):

    def setUp(self):

        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):

        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def temp_file_names(
            self, ending_one="sigmf-data", ending_two="sigmf-meta"):
        name = uuid.uuid4().hex
        if ending_one:
            name_one = name + "." + ending_one
        if ending_two:
            name_two = name + "." + ending_two
        return os.path.join(self.test_dir, name_one), \
            os.path.join(self.test_dir, name_two)

    def test_tag_roundtrip(self):
        # write some data with both capture and annotation data
        freq = 2.4e9
        samp_rate = 100e6
        test_index = 1000
        time = tuple([1222277384, .0625])
        test_a = 22.3125
        test_b = "asdf"
        test_c = True
        test_index_2 = 2000
        test_d = 18.125
        test_e = "jkl;"
        test_f = False
        injector = advanced_tag_injector([
            (0, {"rx_time": time}),
            (0, {"rx_freq": freq}),
            (0, {"rx_rate": samp_rate}),
            (test_index, {"test:a": test_a,
                          "test:b": test_b, "test:c": test_c}),
            (test_index_2, {"test_d": test_d,
                            "test_e": test_e, "test_f": test_f})
            ])
        src = analog.sig_source_c(0, analog.GR_CONST_WAVE, 0, 0, (1 + 1j))
        num_samps = int(1e6)
        head = blocks.head(gr.sizeof_gr_complex, num_samps)
        data_file, json_file = self.temp_file_names()
        file_sink = sigmf.sink("cf32_le",
                               data_file)

        tb = gr.top_block()
        tb.connect(src, head)
        tb.connect(head, injector)
        tb.connect(injector, file_sink)
        tb.start()
        tb.wait()
        # Make sure the data file got written
        self.assertTrue(os.path.exists(data_file), "Data file missing")
        self.assertEqual(os.path.getsize(
            data_file), gr.sizeof_gr_complex * num_samps,
            "Data file incomplete")

        # Ensure that the data exists as we think it should
        with open(json_file, "r") as f:
            meta_str = f.read()
            meta = json.loads(meta_str)
            print(meta)
            self.assertEqual(
                meta["captures"][0]["core:frequency"],
                freq, "Bad metadata, frequency")
            self.assertEqual(meta["global"]["core:sample_rate"],
                             samp_rate, "Bad metadata, samp_rate")

            self.assertEqual(meta["annotations"][0]
                             ["test:a"], test_a, "bad test_a value")
            self.assertEqual(meta["annotations"][0]
                             ["test:b"], test_b, "bad test_b value")
            self.assertEqual(meta["annotations"][0]
                             ["test:c"], test_c, "bad test_c value")
            self.assertEqual(
                meta["annotations"][0]["core:sample_start"],
                test_index, "Bad test index")
            self.assertEqual(meta["annotations"][1]
                             ["unknown:test_d"], test_d, "bad test_d value")
            self.assertEqual(meta["annotations"][1]
                             ["unknown:test_e"], test_e, "bad test_e value")
            self.assertEqual(meta["annotations"][1]
                             ["unknown:test_f"], test_f, "bad test_f value")
            self.assertEqual(
                meta["annotations"][1]["core:sample_start"],
                test_index_2, "Bad test index")

        # Read out the data and check that it matches
        file_source = sigmf.source(data_file, "cf32_le", debug=False)
        collector = tag_collector()
        sink = blocks.vector_sink_c()
        tb = gr.top_block()
        tb.connect(file_source, collector)
        tb.connect(collector, sink)
        tb.start()
        tb.wait()
        collector.assertTagExists(0, "rx_time", time)
        collector.assertTagExists(0, "rx_freq", freq)
        collector.assertTagExists(test_index, "test:a", test_a)
        collector.assertTagExists(test_index, "test:b", test_b)
        collector.assertTagExists(test_index, "test:c", test_c)
        collector.assertTagExists(
            test_index_2, "test_d", test_d)
        collector.assertTagExists(
            test_index_2, "test_e", test_e)
        collector.assertTagExists(
            test_index_2, "test_f", test_f)
