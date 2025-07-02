#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/internet-module.h"
#include "ns3/mmwave-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor.h"
#include "ns3/flow-monitor-helper.h"
#include "ns3/ipv4-flow-classifier.h"
#include "ns3/packet-sink.h"
#include "ns3/point-to-point-helper.h"
#include <fstream>
#include <iostream>

using namespace ns3;
using namespace ns3::mmwave;

NS_LOG_COMPONENT_DEFINE("Raw5gLogger");

std::ofstream logFile;
std::ofstream jsonLogFile;

void LogRawFlowStats(Ptr<FlowMonitor> monitor, Ptr<Ipv4FlowClassifier> classifier) {
    monitor->CheckForLostPackets();
    auto stats = monitor->GetFlowStats();

    for (const auto& flow : stats) {
        Ipv4FlowClassifier::FiveTuple tuple = classifier->FindFlow(flow.first);

        double duration = flow.second.timeLastRxPacket.GetSeconds() - flow.second.timeFirstTxPacket.GetSeconds();
        double throughput = (duration > 0) ? flow.second.rxBytes * 8.0 / duration / 1e6 : 0.0;
        double latency = (flow.second.rxPackets > 0) ? (flow.second.delaySum.GetSeconds() / flow.second.rxPackets) * 1000 : 0.0;
        double jitter = 1.0;     // placeholder raw
        double lossRate = 0.001; // placeholder raw

        logFile << "FlowID: " << flow.first
                << " Src: " << tuple.sourceAddress
                << " Dst: " << tuple.destinationAddress
                << " Port: " << tuple.destinationPort
                << " Latency: " << latency
                << " ms Throughput: " << throughput
                << " Mbps Jitter: " << jitter
                << " LossRate: " << lossRate << "\n";
        logFile.flush();

        jsonLogFile << "{"
                    << "\"flow_id\": " << flow.first << ", "
                    << "\"src\": \"" << tuple.sourceAddress << "\", "
                    << "\"dst\": \"" << tuple.destinationAddress << "\", "
                    << "\"port\": " << tuple.destinationPort << ", "
                    << "\"latency_ms\": " << latency << ", "
                    << "\"throughput_mbps\": " << throughput << ", "
                    << "\"jitter_ms\": " << jitter << ", "
                    << "\"packet_loss\": " << lossRate
                    << "}," << std::endl;
        jsonLogFile.flush();
    }

    Simulator::Schedule(Seconds(1.0), &LogRawFlowStats, monitor, classifier);
}

int main(int argc, char *argv[]) {
    NS_LOG_UNCOND("Starting 5G mmWave simulation");

    CommandLine cmd;
    cmd.Parse(argc, argv);
    logFile.open("raw_kpi_log.txt");
    jsonLogFile.open("raw_kpi_log.json");
    jsonLogFile << "[\n";
    NS_LOG_UNCOND(" KPI log file opened: kpi_log.txt");

    NodeContainer gNbNodes, embbUe, urllcUe, mmtcUe;
    gNbNodes.Create(1);
    embbUe.Create(1);
    urllcUe.Create(1);
    mmtcUe.Create(1);

    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    Ptr<Node> remoteHost = remoteHostContainer.Get(0);

    InternetStackHelper internet;
    internet.InstallAll();

    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", DataRateValue(DataRate("100Gbps")));
    p2ph.SetDeviceAttribute("Mtu", UintegerValue(1500));
    p2ph.SetChannelAttribute("Delay", TimeValue(MilliSeconds(10)));
    NetDeviceContainer internetDevices = p2ph.Install(gNbNodes.Get(0), remoteHost);

    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    ipv4.Assign(internetDevices);

    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(gNbNodes);

    mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                              "Mode", StringValue("Time"),
                              "Time", StringValue("2s"),
                              "Speed", StringValue("ns3::UniformRandomVariable[Min=1.0|Max=3.0]"),
                              "Bounds", StringValue("0|100|0|100"));
    mobility.Install(embbUe);
    mobility.Install(urllcUe);
    mobility.Install(mmtcUe);

    Ptr<MmWaveHelper> mmwaveHelper = CreateObject<MmWaveHelper>();
    mmwaveHelper->SetSchedulerType("ns3::MmWaveFlexTtiMacScheduler");

    NetDeviceContainer enbDevs = mmwaveHelper->InstallEnbDevice(gNbNodes);
    NetDeviceContainer embbDevs = mmwaveHelper->InstallUeDevice(embbUe);
    NetDeviceContainer urllcDevs = mmwaveHelper->InstallUeDevice(urllcUe);
    NetDeviceContainer mmtcDevs = mmwaveHelper->InstallUeDevice(mmtcUe);

    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    ipv4.Assign(enbDevs);
    ipv4.SetBase("10.1.2.0", "255.255.255.0");
    Ipv4InterfaceContainer embbIf = ipv4.Assign(embbDevs);
    ipv4.SetBase("10.1.3.0", "255.255.255.0");
    Ipv4InterfaceContainer urllcIf = ipv4.Assign(urllcDevs);
    ipv4.SetBase("10.1.4.0", "255.255.255.0");
    Ipv4InterfaceContainer mmtcIf = ipv4.Assign(mmtcDevs);
    
    NS_LOG_UNCOND("IPs Assigned:");
    NS_LOG_UNCOND("  eMBB UE IP: " << embbIf.GetAddress(0));
    NS_LOG_UNCOND("  URLLC UE IP: " << urllcIf.GetAddress(0));
    NS_LOG_UNCOND("  mMTC UE IP: " << mmtcIf.GetAddress(0));

    mmwaveHelper->AttachToClosestEnb(embbDevs, enbDevs);
    mmwaveHelper->AttachToClosestEnb(urllcDevs, enbDevs);
    mmwaveHelper->AttachToClosestEnb(mmtcDevs, enbDevs);

    mmwaveHelper->EnableTraces();
    NS_LOG_UNCOND(" Starting UDP traffic generators:");

    UdpServerHelper embbServer(5000);
    ApplicationContainer embbApps = embbServer.Install(embbUe.Get(0));
    UdpClientHelper embbClient(embbIf.GetAddress(0), 5000);
    embbClient.SetAttribute("MaxPackets", UintegerValue(10000));
    embbClient.SetAttribute("Interval", TimeValue(MilliSeconds(10)));
    embbClient.SetAttribute("PacketSize", UintegerValue(1200));
    embbApps.Add(embbClient.Install(gNbNodes.Get(0)));
    embbApps.Start(Seconds(1.0)); embbApps.Stop(Seconds(20.0));
    NS_LOG_UNCOND("  eMBB client setup complete");


    UdpServerHelper urllcServer(5001);
    ApplicationContainer urllcApps = urllcServer.Install(urllcUe.Get(0));
    UdpClientHelper urllcClient(urllcIf.GetAddress(0), 5001);
    urllcClient.SetAttribute("MaxPackets", UintegerValue(10000));
    urllcClient.SetAttribute("Interval", TimeValue(MilliSeconds(1)));
    urllcClient.SetAttribute("PacketSize", UintegerValue(200));
    urllcApps.Add(urllcClient.Install(gNbNodes.Get(0)));
    urllcApps.Start(Seconds(1.0)); urllcApps.Stop(Seconds(20.0));
    NS_LOG_UNCOND("  URLLC client setup complete");

    UdpServerHelper mmtcServer(5002);
    ApplicationContainer mmtcApps = mmtcServer.Install(mmtcUe.Get(0));
    UdpClientHelper mmtcClient(mmtcIf.GetAddress(0), 5002);
    mmtcClient.SetAttribute("MaxPackets", UintegerValue(1000));
    mmtcClient.SetAttribute("Interval", TimeValue(Seconds(5)));
    mmtcClient.SetAttribute("PacketSize", UintegerValue(100));
    mmtcApps.Add(mmtcClient.Install(gNbNodes.Get(0)));
    mmtcApps.Start(Seconds(1.0)); mmtcApps.Stop(Seconds(20.0));
    NS_LOG_UNCOND("  mMTC client setup complete");

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();
    Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowHelper.GetClassifier());
    NS_LOG_UNCOND("FlowMonitor enabled");
    NS_LOG_UNCOND("Simulation running up to 20s...");

    Simulator::Schedule(Seconds(2.0), &LogRawFlowStats, monitor, classifier);

    p2ph.EnablePcapAll("5g-raw-traffic");

    Simulator::Stop(Seconds(20.0));
    Simulator::Run();

    monitor->SerializeToXmlFile("flowmonitor-results.xml", true, true);

    jsonLogFile.seekp(-2, std::ios_base::end);
    jsonLogFile << "\n]\n";
    jsonLogFile.close();
    logFile.close();

    NS_LOG_UNCOND("Raw 5G simulation complete");
    return 0;
}
