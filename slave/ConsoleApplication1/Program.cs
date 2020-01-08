using System;
using System.Collections;
    using System.Collections.Generic;
using System.Net.NetworkInformation;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Net;
    using System.Net.Sockets;

using WindowsInput;

using Razorvine.Pickle;

namespace ConsoleApplication1
{
    class Program
    {
        [DllImport("kernel32.dll")]
        private static extern IntPtr GetConsoleWindow();

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [Serializable]
        private class Package
        {
            private const int SLAVE = 0;
            private const int USER = 1;
            private const int SERVER = 2;
            private const int SU = 3;

            public string TO;
            public string FROM;
            public object[] data;
            public int errcode = 0;
            public int personality = 0;

            public Package(string to, object[] _data)
            {
                TO = to;
                data = _data;
                personality = SLAVE;
            }

            public void set_from(string IP)
            {
                FROM = IP;
            }
        };

        static Dictionary<string, object> Receive_data()
        {
            byte[] buffer;
            Dictionary<string, object> data = new Dictionary<string, object>();
            try
            {
                buffer = listener.Receive(ref groupEP);
                data = (Dictionary<string, object>)unpickler.loads(buffer);//unpickling Python data to dictionary
                if ((string)data["__class__"] != "__main__.Package" && (string)data["__class__"] != "resources.Package")
                {
                    data["errcode"] = -1;
                    Console.WriteLine("Wrong packet form " + groupEP.Address.ToString());
                }
                else
                    data["FROM"] = groupEP.Address.ToString();
            }
            catch (SocketException e)
            {
                Console.WriteLine(e.ToString());
                data["errcode"] = -1;
            }
            catch (PickleException e)
            {
                Console.WriteLine(e.ToString());
                data["errcode"] = -1;
            }

            return data;
        }

        static void Send_data(Package pack)
        {
            byte[] buffer;
            
            try
            {
                buffer = pickler.dumps(pack);//pickling data
                IPAddress ip = IPAddress.Parse(pack.TO);
                IPEndPoint receiver = new IPEndPoint(ip, port);
                sender.SendTo(buffer, receiver);//sending back
            }
            catch (SocketException e)
            {
                Console.WriteLine(e.ToString());
            }
            catch (PickleException e)
            {
                Console.WriteLine(e.ToString());
            }

        }

        static object[] Toggle_visibility(IntPtr handle)
        {
            object[] data = new object[2];
           
            if (visibility)
                ShowWindow(handle, SW_HIDE);
            else
                ShowWindow(handle, SW_SHOW);
            visibility = !visibility;

            data[0] = 22;
            data[1] = visibility;
            return data;
        }


        /*
         * Every package has data built [choose, data, data, ...]
         * Choose determine what to do with the data part
         * 
         * Chooses:
         * -1 error receiving data
         * 0 - close
         * 20 - write data
         * 21 - check if GE is ready for use
         * 22 - toggle visibility
         * 
         */

        //flags
        private const int SW_HIDE = 0;
        private const int SW_SHOW = 5;
        static bool visibility = true;

        //IP variables
        static readonly int port = 57201;
        static UdpClient listener;
        static Socket sender;
        static IPEndPoint groupEP;

        //Pickling
        static Pickler pickler;
        static Unpickler unpickler;


        static void Main(string[] args)
        {
            //getting pointer to the window
            IntPtr handle = GetConsoleWindow();

            //starting GE
            try
            {
                Process.Start("C:\\Program Files\\NVIDIA Corporation\\NVIDIA GeForce Experience\\NVIDIA GeForce Experience.exe");
            }
            catch (System.IO.FileNotFoundException e)
            {
                Console.WriteLine(e.ToString());
            }
            catch (System.ComponentModel.Win32Exception e)
            {
                Console.WriteLine(e.ToString());
            }

            //Hide
            //ShowWindow(handle, SW_HIDE);
            //visibility = false;

            //running socket objects
            listener = new UdpClient(port, AddressFamily.InterNetwork);
            sender = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            groupEP = new IPEndPoint(IPAddress.Any, port);

            //getting pickler objects
            pickler = new Pickler();
            unpickler = new Unpickler();

            //Input simulation
            InputSimulator sim = new InputSimulator();
            IKeyboardSimulator  keybd = sim.Keyboard;

            //received data
            Dictionary<string, object> rec;
            object[] sending_data;
            Package sen_pack;

            ArrayList data;
            string from = "";
            int personality;
            int choose;

            //flags
            bool running = true;


            while (running)
            {
                sending_data = null;

                //receiving data
                rec = Receive_data();
                if ((int)rec["errcode"] == -1)
                    continue;
                data = (ArrayList)rec["data"];
                from = (string)rec["FROM"];
                personality = (int)rec["personality"];
                choose = (int)data[0];

                if (choose == 0)//shutting down the slave
                {
                    running = false;
                    sending_data = new object[2];
                    sending_data[0] = 0;
                    sending_data[1] = true;
                }
                else if (choose == 20)//writing to the window on the top
                {
                    Console.WriteLine("Input of " + (string)data[1]);
                    keybd.TextEntry((string)data[1]);
                    keybd.KeyPress(WindowsInput.Native.VirtualKeyCode.RETURN);
                    sending_data = new object[2];
                    sending_data[0] = 20;
                    sending_data[1] = data[1];
                }
                else if (choose == 21)//checking if Geforce Experience process is working (input when "nvcontainer" is 5)
                {
                    Process[] plist = Process.GetProcessesByName("nvcontainer");
                    Console.WriteLine(plist.Length.ToString());
                    foreach (Process i in plist)
                        Console.WriteLine("Process: {0} - ID: {1}", i.ProcessName, i.Id);

                    sending_data = new object[2]
                        {21, plist.Length };
                }
                else if (choose == 22)//toggle window visibility
                {
                    sending_data = Toggle_visibility(handle);
                }

                //sending back a feedback
                if (sending_data != null)
                {
                    sen_pack = new Package(from, sending_data);//packing
                    Send_data(sen_pack);
                }
            }

            listener.Close();
        }

    }
}
