#pragma comment(lib, "Wlanapi.lib")

#include <iostream>
#include <string>
#include <chrono>
#include <thread>
#include <regex>
#include <vector>
#include <utility>
#include <codecvt>

#include <windows.h>
#include <wlanapi.h>

int main()
{
    unsigned selection;

    std::wstring_convert<std::codecvt_utf8<wchar_t>, wchar_t> converter;
    std::vector<std::pair<std::wstring, std::string>> profileList;
    std::vector<std::pair<PDOT11_SSID, PDOT11_MAC_ADDRESS>> wlanList;

    std::wstring selectedProfile;
    std::string selectedSsid;

    DWORD ret = 0, dwNegotiatedVersion = 0;
    HANDLE hWlan = nullptr;
    PWLAN_INTERFACE_INFO pIfInfo = nullptr;
    PWLAN_INTERFACE_INFO_LIST pIfInfoList = nullptr;
    PWLAN_PROFILE_INFO_LIST pProfileList = nullptr;
    PWLAN_BSS_LIST pBssList = nullptr;

    // open handle
    ret = WlanOpenHandle(2, NULL, &dwNegotiatedVersion, &hWlan);
    if (ret != ERROR_SUCCESS) goto end;

    // get the (first) device
    ret = WlanEnumInterfaces(hWlan, NULL, &pIfInfoList);
    if (ret != ERROR_SUCCESS) goto end;
    if (pIfInfoList->dwNumberOfItems != 1) {
        std::cerr << "No WLAN device found!" << std::endl;
        goto end;
    }

    pIfInfo = &(pIfInfoList->InterfaceInfo[0]);
    std::wcout << "Device: " << pIfInfo->strInterfaceDescription << std::endl;

    ret = WlanScan(hWlan, &pIfInfo->InterfaceGuid, NULL, NULL, NULL);
    if (ret != ERROR_SUCCESS) goto end;

    // select WLAN profile
    ret = WlanGetProfileList(hWlan, &pIfInfo->InterfaceGuid, NULL, &pProfileList);
    if (ret != ERROR_SUCCESS) goto end;

    for (unsigned i = 0; i < pProfileList->dwNumberOfItems; i++) {
        PWLAN_PROFILE_INFO pProfile = &pProfileList->ProfileInfo[i];
        LPWSTR pProfileXml = NULL;
        DWORD dwFlags = NULL, dwGrantedAccess;

        ret = WlanGetProfile(hWlan, &pIfInfo->InterfaceGuid,
            pProfile->strProfileName,
            NULL,
            &pProfileXml,
            &dwFlags,
            &dwGrantedAccess);
        if (ret != ERROR_SUCCESS) continue;

        std::wstring xml(pProfileXml);
        std::wregex regex(L"<name>([0-9A-Za-z-_+ ]+)</name>");
        std::wsmatch match;

        if (std::regex_search(xml, match, regex)) {
            std::wstring profileName(pProfile->strProfileName);
            std::string profileSsid(converter.to_bytes(match[1]));

            std::cout << profileList.size() << ". " << profileSsid;
            std::wcout << " (" << profileName << ")" << std::endl;
            profileList.emplace_back(profileName, profileSsid);
        }
    }

    std::cout << "Which profile? ";
    std::cin >> selection;

    selectedProfile = profileList[selection].first;
    selectedSsid = profileList[selection].second;

    // wait until list populates
    for (int i = 0; i < 10; i++) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        ret = WlanGetNetworkBssList(hWlan, &pIfInfo->InterfaceGuid, NULL, dot11_BSS_type_infrastructure, NULL, NULL, &pBssList);
        if (ret != ERROR_SUCCESS) goto end;
        if (pBssList->dwNumberOfItems > 1) break;
        WlanFreeMemory(pBssList);
    }

    // select BSSID
    for (int i = 0; i < pBssList->dwNumberOfItems; i++) {
         PWLAN_BSS_ENTRY entry = &pBssList->wlanBssEntries[i];
         PDOT11_MAC_ADDRESS pBssid = &entry->dot11Bssid;
         PDOT11_SSID pSsid = &entry->dot11Ssid;
         std::string ssid((char*)pSsid->ucSSID, pSsid->uSSIDLength);

         if (ssid != selectedSsid) continue;

         std::cout << wlanList.size() << ". ";
         printf("%02x:%02x:%02x:%02x:%02x:%02x", (*pBssid)[0], (*pBssid)[1], (*pBssid)[2], (*pBssid)[3], (*pBssid)[4], (*pBssid)[5]);
         std::cout << '\t' << entry->lRssi << '\t' << entry->ulChCenterFrequency << std::endl;

         wlanList.emplace_back(pSsid, pBssid);
    }

    std::cout << "Which BSSID? ";
    std::cin >> selection;

    // connect selected BSSID
    if (selection >= wlanList.size()) {
        std::cerr << "Invalid selection!" << std::endl;
    }
    else {
        PDOT11_SSID targetSsid = wlanList[selection].first;
        PDOT11_MAC_ADDRESS targetBssid = wlanList[selection].second;

        WLAN_CONNECTION_PARAMETERS params;

        params.wlanConnectionMode = wlan_connection_mode_profile;
        params.strProfile = selectedProfile.c_str();
        params.pDot11Ssid = targetSsid;
        params.dot11BssType = dot11_BSS_type_infrastructure;
        params.dwFlags = 0;

        DOT11_BSSID_LIST targetBssidList;
        targetBssidList.Header.Type = NDIS_OBJECT_TYPE_DEFAULT;
        targetBssidList.Header.Revision = DOT11_BSSID_LIST_REVISION_1;
        targetBssidList.Header.Size = sizeof(DOT11_BSSID_LIST);
        targetBssidList.uNumOfEntries = 1;
        targetBssidList.uTotalNumOfEntries = 1;
        memcpy(targetBssidList.BSSIDs[0], targetBssid, sizeof(DOT11_MAC_ADDRESS));
        params.pDesiredBssidList = &targetBssidList;

        ret = WlanConnect(hWlan, &pIfInfo->InterfaceGuid, &params, NULL);
        if (ret != ERROR_SUCCESS) goto end;
    }

    std::cout << "Success!" << std::endl;

end:
    if (pIfInfoList != nullptr) WlanFreeMemory(pIfInfoList);
    if (pProfileList != nullptr) WlanFreeMemory(pProfileList);
    if (pBssList != nullptr) WlanFreeMemory(pBssList);
    WlanCloseHandle(hWlan, NULL);
 
    return ret;
}