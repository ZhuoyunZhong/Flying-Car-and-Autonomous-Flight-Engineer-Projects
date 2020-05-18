import argparse
import time
from enum import Enum

import numpy as np

from udacidrone import Drone
from udacidrone.connection import MavlinkConnection, WebSocketConnection  # noqa: F401
from udacidrone.messaging import MsgID


class States(Enum):
    MANUAL = 0
    ARMING = 1
    TAKEOFF = 2
    WAYPOINT = 3
    LANDING = 4
    DISARMING = 5


class BackyardFlyer(Drone):
    def __init__(self, connection):
        super().__init__(connection)
        self.target_position = [0.0, 0.0, 0.0]
        self.all_waypoints = self.calculate_box()
        self.in_mission = True
        self.check_state = {}

        # initial state
        self.flight_state = States.MANUAL

        # Register all your callbacks here
        self.register_callback(MsgID.LOCAL_POSITION, self.local_position_callback)
        self.register_callback(MsgID.LOCAL_VELOCITY, self.velocity_callback)
        self.register_callback(MsgID.STATE, self.state_callback)

    def local_position_callback(self):
        """
        This triggers when `MsgID.LOCAL_POSITION` is received and self.local_position contains new data
        """
        if self.flight_state == States.TAKEOFF:
            # check if altitude is within 95% of target
            if abs(self.local_position[2] - self.target_position[2]) < abs(0.05*self.target_position[2]):
                self.waypoint_transition()

        if self.flight_state == States.WAYPOINT:
            # check if is within 0.1 m box
            if abs(self.local_position[0] - self.target_position[0]) < 0.2 and \
                abs(self.local_position[1] - self.target_position[1]) < 0.2 and \
                abs(self.local_position[2] - self.target_position[2]) < 0.2:
                if len(self.all_waypoints) > 0:
                    self.waypoint_transition()
                else:
                    self.landing_transition()

        if self.flight_state == States.LANDING:
            if ((self.global_position[2] - self.global_home[2] < 0.1) and
                abs(self.local_position[2]) < 0.01):
                self.disarming_transition()

    def velocity_callback(self):
        """
        This triggers when `MsgID.LOCAL_VELOCITY` is received and self.local_velocity contains new data
        """
        pass

    def state_callback(self):
    if self.in_mission:
        if self.flight_state == States.MANUAL:
            # now just passively waiting for the pilot to change these attributes
            # once the pilot changes, need to update our internal state
            if self.guided:
                self.flight_state = States.ARMING
        elif self.flight_state == States.ARMING:
            if self.armed:
                self.takeoff_transition()
        elif self.flight_state == States.LANDING:
            # check if the pilot has changed the armed and control modes
            # if so (and the script no longer in control) stop the mission
            if not self.armed and not self.guided:
                self.stop()
                self.in_mission = False
        elif self.flight_state == States.DISARMING:
            # no longer want the vehicle to handle the disarming and releasing control
            # that will be done by the pilot
            pass

    def calculate_box(self, target_side=1.0, target_altitude=3.0):
        """
        1. Return waypoints to fly a box
        """
        print("Setting Home")

        # get the current local position -> note we need to change the sign of the down coordinate to be altitude
        cp = np.array([self.local_position[0], self.local_position[1], -self.local_position[2]])  
        target_altitude = 10.0
        target_side = 3.0
        waypoints = [cp + [target_side, 0, -target_altitude, 0], 
                     cp + [target_side, target_side, -target_altitude, 0],
                     cp + [0, target_side, -target_altitude, 0],
                     cp + [0, 0, -target_altitude, 0]]

        return waypoints
                     
    def arming_transition(self):
        """
        1. Take control of the drone
        2. Pass an arming command
        3. Set the home location to current position
        4. Transition to the ARMING state
        """
        print("arming transition")

        self.take_control()
        self.arm()
        # set the current location to be the home position
        self.set_home_position(self.global_position[0],
                               self.global_position[1],
                               self.global_position[2])

        self.flight_state = States.ARMING

    def takeoff_transition(self):
        """
        1. Set target_position altitude to 3.0m
        2. Command a takeoff to 3.0m
        3. Transition to the TAKEOFF state
        """
        print("takeoff transition")

        target_altitude = 3.0
        self.target_position[2] = -target_altitude
        self.takeoff(target_altitude) # super

        self.flight_state = States.TAKEOFF

    def waypoint_transition(self):
        """
        1. Command the next waypoint position
        2. Transition to WAYPOINT state
        """
        print("waypoint transition")

        self.target_position = self.all_waypoints.pop(0)

        north, east, down, heading = self.target_position
        self.cmd_position(north, east, -down, heading)

        self.flight_state = States.WAYPOINT

    def landing_transition(self):
        """
        1. Command the drone to land
        2. Transition to the LANDING state
        """
        print("landing transition")

        self.land()

        self.flight_state = States.LANDING

    def disarming_transition(self):
        """
        1. Command the drone to disarm
        2. Transition to the DISARMING state
        """
        print("disarm transition")

        self.disarm()

        self.flight_state = States.DISARMING

    def manual_transition(self):
        """
        1. Release control of the drone
        2. Stop the connection (and telemetry log)
        3. End the mission
        4. Transition to the MANUAL state
        """
        print("manual transition")

        self.release_control()
        self.stop()
        self.in_mission = False
        self.flight_state = States.MANUAL

    def start(self):
        """
        1. Open a log file
        2. Start the drone connection
        3. Close the log file
        """
        print("Creating log file")
        self.start_log("Logs", "NavLog.txt")
        print("starting connection")
        self.connection.start()
        print("Closing log file")
        self.stop_log()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5760, help='Port number')
    parser.add_argument('--host', type=str, default='127.0.0.1', help="host address, i.e. '127.0.0.1'")
    args = parser.parse_args()

    conn = MavlinkConnection('udp:192.168.1.2:14550', PX4=True, threaded=False)
    #conn = WebSocketConnection('ws://{0}:{1}'.format(args.host, args.port))
    drone = BackyardFlyer(conn)
    time.sleep(2)
    drone.start()
