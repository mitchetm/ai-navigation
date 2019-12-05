#!/usr/bin/env python

import serial
import rospy
import bitstruct
from navigation_msgs.msg import VelAngle
from navigation_msgs.msg import EmergencyStop
from std_msgs.msg import Int8, Bool
cart_port = '/dev/ttyUSB0' #hardcoded depending on computer

class MotorEndpoint(object):

    def __init__(self):
        global cart_port
        self.killswitch = False
        self.current_speed = 0.0
        self.goal_speed = 0.0
        self.goal_angle = 0.0
        self.new_vel = True
        self.debug = False
        self.angle_adjust = 0
        self.stopping_dictionary = {0: False, 1: False, 2: False, 3:False, 4:False}
        self.delay_print = 0
        self.brake = 50
        self.cmd_msg = None
        """ Set up the node. """
        rospy.init_node('motor_endpoint')
        rospy.loginfo("Starting motor node!")
        #Connect to arduino for sending speed
        try:
            rospy.loginfo("remove comments")
            #self.speed_ser = serial.Serial(cart_port, 57600, write_timeout=0)
        except Exception as e:
            print( "Motor_endpoint: " + str(e))
            rospy.logerr("Motor_endpoint: " + str(e))
            #exit(0)

        rospy.loginfo("Speed serial established")
        """
        Connect to arduino for steering
        """
        self.motion_subscriber = rospy.Subscriber('/nav_cmd', VelAngle, self.motion_callback,
                                                  queue_size=10)
        self.stop_subscriber = rospy.Subscriber('/emergency_stop', EmergencyStop,
                                                      self.stop_callback, queue_size=10)
        self.param_subscriber = rospy.Subscriber('/realtime_a_param_change', Int8, self.param_callback, queue_size=10)
        
        self.debug_subscriber = rospy.Subscriber('/realtime_debug_change', Bool, self.debug_callback, queue_size=10)
        
        rate = rospy.Rate(5)

        while not rospy.is_shutdown():
            if self.cmd_msg is not None:
                self.send_to_motors()
            rate.sleep()

    def motion_callback(self, planned_vel_angle):
        self.cmd_msg = planned_vel_angle  
        self.new_vel = True     

    def param_callback(self, msg):
        self.angle_adjust += (msg.data * 10)

    def stop_callback(self, msg):
        self.stopping_dictionary[msg.sender_id] = msg.emergency_stop

    def debug_callback(self, msg):
        self.debug = msg.data


    def send_to_motors(self):
        #The first time we get a new target speed and angle we must convert it
        if self.new_vel:
            self.new_vel = False
            self.cmd_msg.vel *= 50
            self.cmd_msg.vel_curr *= 50
            if self.cmd_msg.vel > 254:
                self.cmd_msg.vel = 254
            if self.cmd_msg.vel < -254:
                self.cmd_msg.vel = -254
            if self.cmd_msg.vel_curr > 254:
                self.cmd_msg.vel_curr = 254
        target_speed = int(self.cmd_msg.vel) #float64
        current_speed = int(self.cmd_msg.vel_curr) #float64
        #adjust the target_angle range from (-70 <-> 70) to (0 <-> 100)
        target_angle = 100 - int(( (self.cmd_msg.angle + 70) / 140 ) * 100)
        #adjust the target angle additionally using a realtime adjustable testing value
        if self.new_vel:
            if target_angle < self.angle_adjust:
                target_angle -= (10 + int(self.angle_adjust/2))
            if target_angle > 100 - self.angle_adjust:
                target_angle += (10 + int(self.angle_adjust/2))
        data = (target_speed,current_speed,target_angle)
        data = bytearray(b'\x00' * 5)
            
        #if debug printing is requested print speed and angle info
        if self.debug:
            self.delay_print -= 1
            if self.delay_print <= 0:
                self.delay_print = 5
                rospy.loginfo("Endpoint Angle: " + str(target_angle))
                rospy.loginfo("Endpoint Speed: " + str(target_speed))

        #for y in self.stopping_dictionary:
            #print(y, self.stopping_dictionary[y])
        #checks if any of the stopping values are True, meaning a service is requesting to stop
        if any(x == True for x in self.stopping_dictionary.values()):
            bitstruct.pack_into('u8u8u8u8u8', data, 0, 42, 21, 0, self.brake, 50) #currently a flat 200 braking number
            if self.brake <= 250:
                self.brake += 4 #how quickly the braking ramps up
        else:
            #reset the brake force slowly incase a new stop message arises immediatly
            if self.brake > 50:
                self.brake -= 1
            #if the target_speed is negative it actually represents desired braking force
            if target_speed < 0:
                bitstruct.pack_into('u8u8u8u8u8', data, 0, 42, 21, 0, abs(target_speed), target_angle)
            else:
                bitstruct.pack_into('u8u8u8u8u8', data, 0, 42, 21, abs(target_speed), 0, target_angle)

        #self.speed_ser.write(data) 


if __name__ == "__main__":
    try:
        MotorEndpoint()
    except rospy.ROSInterruptException:
        pass
