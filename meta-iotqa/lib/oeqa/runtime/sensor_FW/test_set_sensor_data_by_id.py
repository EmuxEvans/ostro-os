'''Verify get sensor data based on its id'''
import os
from oeqa.utils.helper import get_files_dir
from oeqa.oetest import oeRuntimeTest
from oeqa.utils.ddt import ddt, file_data
@ddt
class TestSetSensorDataById(oeRuntimeTest):
    '''Verify sensor data can be returned based on sensor id'''
    @file_data('sensor_id.json')
    def testSetSensorDataById(self, value):
        '''Verify sensor data can be returned based on sensor id'''
        mkdir_path = "mkdir -p /opt/sensor-test/apps/"
        (status, output) = self.target.run(mkdir_path)
        copy_to_path = os.path.join(get_files_dir(), 'test_set_sensor_data_by_id')
        (status, output) = self.target.copy_to(copy_to_path, "/opt/sensor-test/apps/")
        #run test set sensor data by id and show it's information
        cmd = "/opt/sensor-test/apps/test_set_sensor_data_by_id"
        client_cmd = "%s %s"%(cmd, str(value))
        (status, output) = self.target.run(client_cmd)
        print output
        self.assertEqual(status, 1, msg="Error messages: %s" % output)
