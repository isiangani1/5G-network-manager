#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/internet-module.h"
#include "ns3/mmwave-helper.h"
#include "ns3/mmwave-point-to-point-epc-helper.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/ipv4-static-routing-helper.h"
#include "ns3/point-to-point-helper.h"

#include <fstream>
#include <iostream>

using namespace ns3;
using namespace mmwave;

NS_LOG_COMPONENT_DEFINE("Refactored5gSim");

std::ofstream logFile;
std::ofstream jsonLogFile;

void LogRawFlowStats(Ptr<FlowMonitor> monitor, Ptr<Ipv4FlowClassifier> classifier)
{
    monitor->CheckForLostPackets();
    auto stats = monitor->GetFlowStats();

    NS_LOG_UNCOND("Logging raw flow stats...");
    for (const auto &flow : stats)
    {
        Ipv4FlowClassifier::FiveTuple tuple = classifier->FindFlow(flow.first);

        double duration = flow.second.timeLastRxPacket.GetSeconds() - flow.second.timeFirstTxPacket.GetSeconds();
        double throughput = (duration > 0) ? flow.second.rxBytes * 8.0 / duration / 1e6 : 0.0;
        double latency = (flow.second.rxPackets > 0) ? (flow.second.delaySum.GetSeconds() / flow.second.rxPackets) * 1000 : 0.0;

        logFile << "FlowID: " << flow.first
                << " Src: " << tuple.sourceAddress
                << " Dst: " << tuple.destinationAddress
                << " Port: " << tuple.destinationPort
                << " Latency: " << latency << "ms"
                << " Throughput: " << throughput << "Mbps\n";
        logFile.flush();

        jsonLogFile << "{"
                    << "\"flow_id\": " << flow.first << ", "
                    << "\"src\": \"" << tuple.sourceAddress << "\", "
                    << "\"dst\": \"" << tuple.destinationAddress << "\", "
                    << "\"port\": " << tuple.destinationPort << ", "
                    << "\"latency_ms\": " << latency << ", "
                    << "\"throughput_mbps\": " << throughput
                    << "}," << std::endl;
        jsonLogFile.flush();
    }

    Simulator::Schedule(Seconds(1.0), &LogRawFlowStats, monitor, classifier);
}

int main(int argc, char *argv[])
{
    NS_LOG_UNCOND(">>> Starting 5G mmWave simulation setup...");

    CommandLine cmd;
    cmd.Parse(argc, argv);

    logFile.open("raw_kpi_log.txt");
    jsonLogFile.open("raw_kpi_log.json");
    jsonLogFile << "[\n";
    NS_LOG_UNCOND(">>> KPI log files opened (TXT & JSON)");

    Ptr<MmWaveHelper> mmwaveHelper = CreateObject<MmWaveHelper>();
    mmwaveHelper->SetSchedulerType("ns3::MmWaveFlexTtiMacScheduler");
    NS_LOG_UNCOND(">>> MmWaveHelper configured with FlexTti scheduler");

    Ptr<MmWavePointToPointEpcHelper> epcHelper = CreateObject<MmWavePointToPointEpcHelper>();
    mmwaveHelper->SetEpcHelper(epcHelper);
    Ptr<Node> pgw = epcHelper->GetPgwNode();

    NodeContainer enbs, ues;
    enbs.Create(1);
    ues.Create(1);

    NodeContainer remoteHostContainer;
    remoteHostContainer.Create(1);
    Ptr<Node> remoteHost = remoteHostContainer.Get(0);
    InternetStackHelper internet;
    internet.Install(ues);
    internet.Install(remoteHost);

    PointToPointHelper p2ph;
    p2ph.SetDeviceAttribute("DataRate", StringValue("100Gbps"));
    p2ph.SetChannelAttribute("Delay", StringValue("2ms"));
    NetDeviceContainer p2pDevs = p2ph.Install(pgw, remoteHost);

    Ipv4AddressHelper ipv4;
    ipv4.SetBase("1.0.0.0", "255.0.0.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(p2pDevs);
    Ipv4Address remoteHostAddr = interfaces.GetAddress(1);
    NS_LOG_UNCOND(">>> RemoteHost IP: " << remoteHostAddr);

    Ipv4StaticRoutingHelper ipv4RoutingHelper;
    Ptr<Ipv4StaticRouting> remoteHostRouting = ipv4RoutingHelper.GetStaticRouting(remoteHost->GetObject<Ipv4>());
    remoteHostRouting->AddNetworkRouteTo(Ipv4Address("7.0.0.0"), Ipv4Mask("255.0.0.0"), 1);

    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(enbs);
    mobility.Install(ues);
    NS_LOG_UNCOND(">>> Mobility assigned");

    NetDeviceContainer enbDevs = mmwaveHelper->InstallEnbDevice(enbs);
    NetDeviceContainer ueDevs = mmwaveHelper->InstallUeDevice(ues);

    Ipv4InterfaceContainer ueIpIfaces = epcHelper->AssignUeIpv4Address(NetDeviceContainer(ueDevs));
    Ipv4Address ueAddr = ueIpIfaces.GetAddress(0);
    NS_LOG_UNCOND(">>> UE assigned IP: " << ueAddr);

    mmwaveHelper->AttachToClosestEnb(ueDevs, enbDevs);
    NS_LOG_UNCOND(">>> Devices installed and UE attached to closest eNB");

    for (uint32_t i = 0; i < ues.GetN(); ++i)
    {
        Ptr<Ipv4StaticRouting> ueRouting = ipv4RoutingHelper.GetStaticRouting(ues.Get(i)->GetObject<Ipv4>());
        ueRouting->SetDefaultRoute(epcHelper->GetUeDefaultGatewayAddress(), 1);
        //ueRouting->AddNetworkRouteTo(Ipv4Address("1.0.0.0"), Ipv4Mask("255.0.0.0"), 1);
    }

    uint16_t port = 12345;
    UdpServerHelper server(port);
    ApplicationContainer serverApps = server.Install(remoteHost);
    serverApps.Start(Seconds(1.0));
    serverApps.Stop(Seconds(20.0));
    NS_LOG_UNCOND(">>> UDP Server started on RemoteHost");

    UdpClientHelper client(remoteHostAddr, port);
    client.SetAttribute("MaxPackets", UintegerValue(1000000));
    client.SetAttribute("Interval", TimeValue(MilliSeconds(10)));
    client.SetAttribute("PacketSize", UintegerValue(1200));
    ApplicationContainer clientApps = client.Install(ues.Get(0));
    clientApps.Start(Seconds(1.0));
    clientApps.Stop(Seconds(20.0));
    NS_LOG_UNCOND(">>> UDP Client started on UE targeting RemoteHost");

    mmwaveHelper->EnableTraces();
    p2ph.EnablePcapAll("5g-raw-traffic");
    NS_LOG_UNCOND(">>> PCAP tracing enabled");

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();
    Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowHelper.GetClassifier());

    Simulator::Schedule(Seconds(2.0), &LogRawFlowStats, monitor, classifier);
    NS_LOG_UNCOND(">>> FlowMonitor and periodic logger scheduled");

    Simulator::Stop(Seconds(21.0));
    NS_LOG_UNCOND(">>> Simulation running...");
    Simulator::Run();

    Ptr<UdpServer> udpServer = DynamicCast<UdpServer>(serverApps.Get(0));
    NS_LOG_UNCOND("Packets received by UDP server: " << udpServer->GetReceived());

    monitor->SerializeToXmlFile("flowmonitor-results.xml", true, true);
    NS_LOG_UNCOND(">>> FlowMonitor results saved");

    jsonLogFile.seekp(-2, std::ios_base::end);
    jsonLogFile << "\n]\n";
    jsonLogFile.close();
    logFile.close();

    NS_LOG_UNCOND(">>> Simulation complete. Logs closed.");
    Simulator::Destroy();
    return 0;
}
